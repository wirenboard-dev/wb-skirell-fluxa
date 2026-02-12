#!/usr/bin/env python3

import os
import re
import sys
import json
import hashlib
import requests

from cgi import FieldStorage

ICONDB_FILE_PATH = "/usr/lib/cgi-bin/skirell-icons.json"
CONFIG_FILE_PATH = "/etc/wb-skirell-fluxa.conf"
SCHEMA_FILE_PATH = "/usr/share/wb-mqtt-confed/schemas/wb-skirell-fluxa.schema.json"
 
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

def update_icons_file():
	packs = {
		"https://cdn.jsdelivr.net/npm/@mdi/font@latest/css/materialdesignicons.min.css": r'\.(mdi-[a-z0-9-]+)::before\s*\{\s*content:\s*"\\?([a-fA-F0-9]+)"\s*\}'
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
					object[key] = "/devices/{}/controls/{}".format(match.group(1), match.group(2))
				elif 'command_' in key:
					object[key] = "/devices/{}/controls/{}/on".format(match.group(1), match.group(2))

			if key.startswith('icon'):
				name = object[key]

				if not any(name.startswith(pack) for pack in ['mdi']):
					name = 'mdi-' + name

				object[key] = chr(int(icons[name], 16))

	return object

def find_devices():
	link = "<a href='./fluxa/{}' target='_blank' style='vertical-align: middle; margin-left: 5px' class='text-muted' title='Скачать'><i class='glyphicon glyphicon-save'></i></a>"
	data = json.loads(sys.stdin.read())

	for index, panel in enumerate(data.get('panels', [])):
		data['panels'][index]['link'] = link.format(panel.get('id'))

	json.dump(data, sys.stdout, ensure_ascii=False, indent=4)

def update_checksum():
	data = json.loads(sys.stdin.read())

	for index, panel in enumerate(data.get('panels', [])):
		screens = panel.get('screens', [])

		hash = hashlib.md5(json.dumps({'screens': screens}).encode('utf-8')).hexdigest()

		if panel.get('crc') is None or panel['crc'] != hash:
			data['panels'][index]['crc'] = hash

		if panel.get('link'): del panel['link']

	json.dump(data, sys.stdout, ensure_ascii=False, indent=4)

def generate_json(id):
	try:
		with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as file:
			data = json.load(file)
	except Exception as error:
		send_response('500 Internal Server Error', 'text/html', HTML_TEMPLATE.replace('%s', f"{error}"))
		sys.exit(1)

	try:
		with open(SCHEMA_FILE_PATH, 'r', encoding='utf-8') as file:
			schema = json.load(file).get('definitions', {})
	except Exception as error:
		send_response('500 Internal Server Error', 'text/html', HTML_TEMPLATE.replace('%s', f"{error}"))
		sys.exit(1)

	screens = []

	for panel in data.get('panels', []):
		if id.upper() == panel.get('id', '').upper():
			screens.extend(panel.get('screens', []))

	if len(screens):
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

					if 'variant' in data and 'type' in data['variant']: del data['variant']['type']

					block['data'] = process_topics(data)
					page['blocks'][j - 1] = block

		return {'screens': screens}
	else:
		return

if __name__ == "__main__":

	try:
		with open(ICONDB_FILE_PATH, 'r', encoding='utf-8') as file:
			icons = json.load(file)
	except Exception as error:
		pass

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
				if (data := generate_json(id)):
					send_response('200 OK', 'application/octet-stream', None, id)
					json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
				else:
					send_response('404 Not Found', 'text/html', HTML_TEMPLATE.replace('%s', 'Конфигурация для этой панели еще не добавлена.'))
		else:
			send_response('202 Accepted', 'text/html', HTML_TEMPLATE.replace('%s', 'Для получения конфигурации требуется ID панели!'))