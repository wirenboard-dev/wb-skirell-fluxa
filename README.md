# wb-skirell-fluxa [![--](https://img.shields.io/badge/информация-о_панели-informational)](https://skirell.ru/service/fluxa) [![--](https://img.shields.io/badge/полная-документация-success)](https://docs-fluxa.skirell.ru)

Конфигуратор панелей Skirell-Fluxa для Wiren Board

## Возможности

- Первичная загрузка существующей конфигурации из панелей
- Отправка измененных конфигураций после редактирования
- Использование коротких топиков из WB

## Установка

Скачайте файл пакета на Wiren Board и установите с помощью dpkg одной командой:

#### Wirenboard 8

```sh
wget https://github.com/skirell/wb-skirell-fluxa/releases/latest/download/wb-skirell-fluxa_arm64.deb && \
dpkg -i wb-skirell-fluxa_arm64.deb && rm wb-skirell-fluxa_arm64.deb
```

#### Wirenboard 6/7

```sh
wget https://github.com/skirell/wb-skirell-fluxa/releases/latest/download/wb-skirell-fluxa_armhf.deb && \
dpkg -i wb-skirell-fluxa_armhf.deb && rm wb-skirell-fluxa_armhf.deb
```

> **Внимание!** После установки будет перезагружен сервис `nginx` для активации всех функций.

## Удаление

Выполните слудующую команду:

```sh
apt remove wb-skirell-fluxa -y
```
