# MLTC

Контроль минимального времени слоя для Klipper.

После перезагрузки модуль выключен. Переключение: `CHANGE_MLTC` (или `MLTC_ENABLE` / `MLTC_DISABLE`).

## Установка

```bash
cd ~ && \
git clone https://github.com/Transistor427/MLTC.git -b v2 && \
ln -sf ~/MLTC/minimum_layer_time_control.py ~/klipper/klippy/extras/minimum_layer_time_control.py && \
cp ~/MLTC/minimum_layer_time_control.cfg ~/printer_data/config/klipper-config
```

В `printer.cfg` добавьте:

```
[include klipper-config/minimum_layer_time_control.cfg]
```

Перезапустите Klipper (`FIRMWARE_RESTART`).

## Конфигурация

```
[minimum_layer_time_control]
min_layer_time: 20
```

`min_layer_time` — минимальное время слоя в секундах.

## Использование

Для кнопки в интерфейсе используйте `CHANGE_MLTC` (состояние хранится в `change_mltc` через `save_variables`).
В стартовый G-код при необходимости добавьте `MLTC_ENABLE`.

| Команда | Действие |
|---|---|
| `CHANGE_MLTC` | Переключить контроль |
| `MLTC_ENABLE` | Включить контроль |
| `MLTC_DISABLE` | Выключить контроль |
