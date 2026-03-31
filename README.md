# wb-skirell-fluxa

Конфигуратор панелей [Skirell Fluxa](https://skirell.ru/panel) для Wiren Board

## Возможности

- Первичная загрузка существующей конфигурации из панелей
- Отправка измененных конфигураций после редактирования
- Использование коротких топиков из WB

## Установка

Скачайте файл пакета на Wiren Board и установите с помощью dpkg:

#### Wirenboard 8

```sh
wget https://github.com/wirenboard-dev/wb-skirell-fluxa/releases/latest/download/wb-skirell-fluxa_arm64.deb && \
dpkg -i wb-skirell-fluxa_arm64.deb && rm wb-skirell-fluxa_arm64.deb
```

#### Wirenboard 6/7

```sh
wget https://github.com/wirenboard-dev/wb-skirell-fluxa/releases/latest/download/wb-skirell-fluxa_armhf.deb && \
dpkg -i wb-skirell-fluxa_armhf.deb && rm wb-skirell-fluxa_armhf.deb
```

## Удаление

Выполните слудующую команду:

```sh
apt remove wb-skirell-fluxa -y
```