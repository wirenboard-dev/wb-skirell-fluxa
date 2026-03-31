#!/usr/bin/env python3

import os
import io
import re
import sys
import json
import copy
import hashlib
import requests
import subprocess

from cgi import FieldStorage
from datetime import datetime

ICONDB_FILE_PATH = '/usr/lib/cgi-bin/skirell-icons.json'
CONFIG_FILE_PATH = '/etc/wb-skirell-fluxa.conf'
SCHEMA_FILE_PATH = '/usr/share/wb-mqtt-confed/schemas/wb-skirell-fluxa.schema.json'
 
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
	<meta charset="utf-8">
	<title>Skirell Fluxa</title>
</head>

<body>
	<main>
		<h1>%s</h1>
	</main>

	<style>
		body {font-family: "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif; color: #888; margin: 0; display: table; width: 100%; height: 100vh; text-align: center}
		main {display: table-cell; vertical-align: middle}
		main h1 {font-size: 32px; display: inline-block; padding-right: 12px; animation: type .5s alternate infinite}
		@keyframes type {from {box-shadow: inset -3px 0px 0px #888;} to {box-shadow: inset -3px 0px 0px transparent}}
	</style>
</body>
</html>"""

icons = None
glyph = None
place = {}

def update_icons_file():
	packs = {
		'https://cdn.jsdelivr.net/npm/@mdi/font@latest/css/materialdesignicons.min.css': r'\.(mdi-[a-z0-9-]+)::before\s*\{\s*content:\s*"\\?([a-fA-F0-9]+)"\s*\}'
	}

	result = {}

	for url, pattern in packs.items():
		response = requests.get(url)

		if response.status_code != 200:
			sys.stdout.write(f'Skirell-Fluxa: Не удалось обработать {url}\n')
			return

		find = re.compile(pattern).findall(response.text)

		sys.stdout.write(f'Skirell-Fluxa: В файле {url} найдено {len(find)} иконок\n')

		for name, code in find:
			result[name] = code
	try:
		with open(ICONDB_FILE_PATH, 'w', encoding='utf-8') as file:
			json.dump(result, file, ensure_ascii=False, indent=4)
	except Exception as error:
		sys.stdout.write(f'Skirell-Fluxa: Ошибка при работе с {ICONDB_FILE_PATH} = {error}\n')
		sys.exit(1)

def send_response(code, type, content='', file=False):
	sys.stdout.write(f'Status: {code}\r\n')

	if file: sys.stdout.write(f'Content-Disposition: attachment; filename="data_{file}.json"\r\n')

	sys.stdout.write(f'Content-Type: {type}; charset=utf-8\r\n\r\n')

	if content: sys.stdout.write(content)

def process_topics(object):
	if isinstance(object, dict):
		for key in list(object.keys()):
			topic = object[key]
			object[key] = process_topics(topic)

			if '_topic' in key and (match := re.match(r'^([^/+#]+)/([^/+#]+)$', topic)):
				if 'state_' in key:
					object[key] = '/devices/{}/controls/{}'.format(match.group(1), match.group(2))
				elif 'command_' in key:
					object[key] = '/devices/{}/controls/{}/on'.format(match.group(1), match.group(2))

			if key.startswith('icon'):
				name = object[key]

				if not any(name.startswith(pack) for pack in ['mdi']): name = 'mdi-' + name
				if not icons.get(name): name = 'mdi-border-radius'

				object[key] = chr(int(icons[name], 16))

			if object[key] == []: object[key] = None

	elif isinstance(object, list):
		for key in range(len(object)):
			object[key] = process_topics(object[key])

	return object

def find_devices():
	link = "<a href='./fluxa/{}' target='_blank' style='vertical-align: middle; margin-left: 5px' class='text-muted' title='Скачать'><i class='glyphicon glyphicon-save'></i></a>"
	data = json.loads(sys.stdin.read())

	for i, panel in enumerate(data.get('panels', [])):
		data['panels'][i]['link'] = link.format(panel.get('id'))

	try:
		command = 'timeout 1 mosquitto_sub -v -t /devices/+/controls/id/meta/type | grep -oP "Skirell-Fluxa-\\K[0-9A-F]+"'
		devices = subprocess.run(command, shell=True, capture_output=True, text=True, check=True).stdout
	except subprocess.CalledProcessError as error:
		pass
	else:
		for id in devices.splitlines():
			if not any(panel.get('id') == id for panel in data.get('panels', [])):
				if (config := import_config(place[id])):
					crc = hashlib.md5(json.dumps({'screens': config}, sort_keys=True).encode('utf-8')).hexdigest()

					data['panels'].append({'id': id, 'name': '', 'upload': '', 'screens': config, 'crc': crc})
				else:
					data['panels'].append({'id': id, 'name': '', 'upload': '', 'screens': [], 'crc': ''})

	json.dump(data, sys.stdout, ensure_ascii=False, indent=4)

def update_checksum():
	data = json.loads(sys.stdin.read())

	for i, panel in enumerate(data.get('panels', [])):
		screens = panel.get('screens', [])
		hash = hashlib.md5(json.dumps({'screens': screens}, sort_keys=True).encode('utf-8')).hexdigest()

		if panel.get('crc') is None or panel['crc'] != hash:
			config = generate_json(copy.deepcopy(screens))
			target = place.get(panel.get('id'))

			if config is None:
				panel['upload'] = ''
			elif not target:
				panel['upload'] = 'no ip-address'
			else:
				try:
					check = requests.get(f'http://{target}/', timeout=2)

					if check.status_code == 200:
						try:
							response = requests.post(
								url=f'http://{target}/upload',
								files={'file': ('data.json', io.BytesIO(json.dumps(config).encode('utf-8')), 'application/json')}
							)

							if response.status_code == 200:
								panel['upload'] = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
								panel['crc'] = hash
							else:
								panel['upload'] = 'trasfer fail'

						except Exception as error: pass
					else:
						panel['upload'] = 'no connection'
						panel['crc'] = hash + '!'

				except requests.RequestException: pass

		if panel.get('link'): del panel['link']

	json.dump(data, sys.stdout, ensure_ascii=False, indent=4)

def generate_json(screens):
	if len(screens):
		try:
			with open(SCHEMA_FILE_PATH, 'r', encoding='utf-8') as file:
				schema = json.load(file).get('definitions', {})
		except Exception as error:
			send_response('500 Internal Server Error', 'text/html', HTML_TEMPLATE.replace('%s', f"SCHEMA: {error}"))
			sys.exit(1)

		for i, screen in enumerate(screens, start=1):
			page = {'page': i}
			page.update(screen)
			screens[i - 1] = page

			if 'blocks' in page:
				for j, item in enumerate(page['blocks'], start=1):
					block = {'block': j}
					block.update(item)

					fields = schema.get('block_{}'.format(block['type']), {}).get('properties', {})

					for param, custom in fields.items():
						optional = custom.get('options', {}).get('show_opt_in')

						if optional is True and param not in block: block[param] = ""

					data = {k: v for k, v in block.items() if k not in ('block', 'type')}

					for key in data: del block[key]

					if 'variant' in data:
						arrays = {'fan_modes': 'mode', 'modes': 'mode', 'sensors': 'sensor'}

						for param, value in data['variant'].items():
							if value and param in arrays and isinstance(value, list):
								converted = {}

								for i, item in enumerate(value, start=1):
									name = f"{arrays[param]}_{i}"
									converted[name] = item

								data['variant'][param] = converted

						if 'type' in data['variant']: del data['variant']['type']
						if 'cover' in block['type'] and not 'lameli' in data['variant']: data['variant']['lameli'] = None

					if 'music' in block['type'] and 'channels' in data:
						if (value := data['channels'])and isinstance(value, list):
							converted = {}

							for i, item in enumerate(value, start=1):
								name = f"channel_{i}"
								converted[name] = item

							data['channels'] = converted

					block['data'] = process_topics(data)
					page['blocks'][j - 1] = block
		return {'screens': screens}
	else:
		return

def generate_file(id):
	try:
		with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as file:
			data = json.load(file)
	except Exception as error:
		send_response('500 Internal Server Error', 'text/html', HTML_TEMPLATE.replace('%s', f"CONFIG: {error}"))
		sys.exit(1)

	screens = []

	for panel in data.get('panels', []):
		if id.upper() == panel.get('id', '').upper():
			screens.extend(panel.get('screens', []))

	return generate_json(screens)

def import_config(url):
	def clean_element(value, key=None):
		if isinstance(value, dict):
			return {k: clean_element(v, k) for k, v in value.items() if v is not None and v != ""}
		elif isinstance(value, list):
			return [clean_element(i) for i in value if i is not None]
		else:
			if '_topic' in key and (match := re.search(r'/devices/([^/]+)/controls/([^/]+)', value)):
				value = '{}/{}'.format(match.group(1), match.group(2))

			if 'icon' in key:
				value = format(ord(value), 'X')
				value = glyph.get(value, 'mdi-border-radius')
				value = value.replace('mdi-', '')

			if 'min_target' in key or 'max_target' in key:
				value = int(value)

			return value

	try:
		check = requests.get(f'http://{url}', timeout=2)
		
		if check.status_code == 200:
			try:
				response = requests.get(f'http://{url}/download')
				
				if response.status_code == 200:
					data = response.json()

					for screen in data['screens']:
						if 'page' in screen:
							del screen['page']

						if 'blocks' in screen:
							for i, block in enumerate(screen['blocks']):

								if 'block' in block:
									del block['block']

								if 'data' in block:
									block.update(block.get('data', {}))

									del block['data']

								if 'variant' in block:
									if (variant := block['variant']) and isinstance(variant, dict):
										for item in ['fan_modes', 'modes', 'sensors', 'channels']:
											if item in variant and isinstance(variant[item], dict):
												variant[item] = list(variant[item].values())

									variant['type'] = block.get('variant_type', '')

								if 'music' in block['type'] and 'channels' in block:
									if isinstance(block['channels'], dict):
										block['channels'] = list(block['channels'].values())

								screen['blocks'][i] = clean_element(block)
					return data['screens']
			except requests.RequestException:
				return []
			except json.JSONDecodeError:
				return []
	except requests.RequestException: pass

	return []

if __name__ == "__main__":

	try:
		with open(ICONDB_FILE_PATH, 'r', encoding='utf-8') as file:
			icons = json.load(file)
			glyph = {v: k for k, v in icons.items()}
	except Exception as error:
		pass

	try:
		command = 'timeout 1 mosquitto_sub -v -t /devices/+/controls/ip | grep -oP "Skirell-Fluxa-\K[0-9A-F]+|[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+"'
		devices = subprocess.run(command, shell=True, capture_output=True, text=True, check=True).stdout
	except subprocess.CalledProcessError as error:
		pass
	else:
		lines = devices.splitlines()

		for i in range(0, len(lines), 2):
			key = lines[i]
			value = lines[i+1] if i+1 < len(lines) else ''
			place[key] = value

	if len(sys.argv) > 1 and sys.argv[1] == '-icons':
		update_icons_file()
	elif len(sys.argv) > 1 and sys.argv[1] == '-load':
		find_devices()
	elif len(sys.argv) > 1 and sys.argv[1] == '-save':
		update_checksum()
	else:
		if 'id' in (form := FieldStorage(encoding='utf-8')):
			id = form.getvalue('id')

			if not re.match(r"^[0-9A-Fa-f]{12}$", id):
				send_response('400 Bad Request', 'text/html', HTML_TEMPLATE.replace('%s', 'Указан некорректный ID панели!'))
			else:
				if (data := generate_file(id)):
					send_response('200 OK', 'application/octet-stream', None, id)
					json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
				else:
					send_response('404 Not Found', 'text/html', HTML_TEMPLATE.replace('%s', 'Конфигурация для этой панели еще не добавлена.'))
		else:
			send_response('202 Accepted', 'text/html', HTML_TEMPLATE.replace('%s', 'Для получения конфигурации требуется ID панели!'))