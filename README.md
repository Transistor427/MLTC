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
park_x: 0
park_y: 0
z_hop: 5
travel_speed: 150
z_speed: 15
```

| Параметр | Описание |
|---|---|
| `min_layer_time` | Минимальное время слоя, с |
| `park_x` / `park_y` | Координаты отъезда головы на время ожидания |
| `z_hop` | Подъём по Z перед отъездом, мм |
| `travel_speed` | Скорость перемещения XY, мм/с |
| `z_speed` | Скорость подъёма/опускания Z, мм/с |

При нехватке времени слоя: подъём Z → парковка XY → ожидание → возврат XY → опускание Z.

## Использование

Для кнопки в интерфейсе используйте `CHANGE_MLTC` (состояние хранится в `change_mltc` через `save_variables`).
Перед печатью контроль должен быть включён (`CHANGE_MLTC` / `MLTC_ENABLE`).

### Слайсер и макрос смены слоя

В G-коде смены слоя слайсера (Orca/Prusa/SuperSlicer):

```
_AFTER_LAYER_CHANGE Z={layer_z} NUM_LAYER={layer_num}
```

В конфиге принтера в макрос `_AFTER_LAYER_CHANGE` добавьте вызов MLTC (остальной код макроса оставьте как есть):

```
[gcode_macro _AFTER_LAYER_CHANGE]
gcode:
    ; ... ваш существующий код ...
    {% if params.NUM_LAYER is defined %}
    MINIMUM_LAYER_TIME_CONTROL_LAYER LAYER={params.NUM_LAYER}
    {% endif %}
```

Без `NUM_LAYER` в вызове из слайсера и без этой строки в макросе модуль не узнаёт о смене слоя и паузу не ставит.

| Команда | Действие |
|---|---|
| `CHANGE_MLTC` | Переключить контроль |
| `MLTC_ENABLE` | Включить контроль |
| `MLTC_DISABLE` | Выключить контроль |
| `MINIMUM_LAYER_TIME_CONTROL_LAYER` | Сообщить номер слоя (`LAYER=` / `NUM_LAYER=`) |
