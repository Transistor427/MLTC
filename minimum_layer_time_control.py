# Расширение контроля минимального времени слоя с управлением
#
# This file may be distributed under the terms of the GNU GPLv3 license.

import logging
import time

class MinLayerTimer:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object('gcode')
        # Параметры конфигурации
        self.min_layer_time = config.getfloat('min_layer_time', 20.0)
        self.debug_level = config.getint('debug_level', 1, minval=0, maxval=3)
        self.enabled = config.getboolean('enabled', True)
        # Состояние печати
        self.is_printing = False
        self.current_layer = 0
        self.layer_start_time = 0
        self.last_layer_time = 0
        self.next_layer_check = 0
        # Регистрация обработчиков
        self.printer.register_event_handler("klippy:started", self._handle_started)
        self.printer.register_event_handler("klippy:disconnect", self._handle_disconnect)
        self.printer.register_event_handler("idle_timeout:printing",
                                          self._handle_printing_start)
        # Перехват G-кодов для отслеживания слоев
        self.gcode.register_command('M117', None)
        self.gcode.register_command('M117', self.cmd_M117)
        self.gcode.register_command('SET_PRINT_STATS_INFO', None)
        self.gcode.register_command('SET_PRINT_STATS_INFO', self.cmd_SET_PRINT_STATS_INFO)
        # Команды управления
        self.gcode.register_command(
            'MINIMUM_LAYER_TIME_CONTROL_ENABLE',
            self.cmd_ENABLE,
            desc="Включение контроля времени слоя"
        )
        self.gcode.register_command(
            'MINIMUM_LAYER_TIME_CONTROL_DISABLE',
            self.cmd_DISABLE,
            desc="Выключение контроля времени слоя"
        )
        # Статус-таймер
        self.status_timer = None
        # Логгер
        self.logger = logging.getLogger("min_layer_timer")
        self._log(1, "Модуль инициализирован")
        self._log(1, "Минимальное время слоя: %.1f сек" % self.min_layer_time)
        self._log(1, "Состояние: %s" % ("ВКЛЮЧЕН" if self.enabled else "ВЫКЛЮЧЕН"))
    def _handle_started(self):
        self._log(1, "Принтер запущен")
        self.status_timer = self.reactor.register_timer(
            self._status_update,
            self.reactor.NOW
        )
    def _handle_disconnect(self):
        self._log(1, "Принтер отключен")
        if self.status_timer is not None:
            self.reactor.unregister_timer(self.status_timer)
            self.status_timer = None
    def _handle_printing_start(self, print_time):
        self.is_printing = True
        self.current_layer = 0
        self.layer_start_time = self.reactor.monotonic()
        self.last_layer_time = 0
        self._log(1, "Печать начата, слой: 0")
    def cmd_SET_PRINT_STATS_INFO(self, gcmd):
        # Обработка команды PrusaSlicer/SuperSlicer
        if gcmd.get('CURRENT_LAYER', None) is not None:
            try:
                new_layer = int(gcmd.get('CURRENT_LAYER'))
                self._handle_layer_change(new_layer)
            except ValueError:
                pass
        gcmd.ack()
    def cmd_M117(self, gcmd):
        # Обработка команды Cura
        msg = gcmd.get_commandline()
        if "LAYER:" in msg:
            try:
                parts = msg.split("LAYER:")
                if len(parts) > 1:
                    new_layer = int(parts[1].strip())
                    self._handle_layer_change(new_layer)
            except ValueError:
                pass
        gcmd.ack()
    def _handle_layer_change(self, new_layer):
        if not self.is_printing or not self.enabled:
            return
        current_time = self.reactor.monotonic()
        # Вычисляем время предыдущего слоя
        if self.current_layer > 0 and self.layer_start_time > 0:
            self.last_layer_time = current_time - self.layer_start_time
            self._log(1, "Слой %d занял %.1f сек (минимум: %.1f сек)" % (
                self.current_layer, self.last_layer_time, self.min_layer_time))
            # Проверяем, нужно ли приостановить печать
            if self.last_layer_time < self.min_layer_time:
                wait_time = self.min_layer_time - self.last_layer_time
                self._log(1, "Требуется пауза: %.1f сек" % wait_time)
                self._schedule_pause_and_resume(wait_time)
        # Начинаем новый слой
        self.current_layer = new_layer
        self.layer_start_time = current_time
        self.next_layer_check = current_time + 1.0
        self._log(1, "===== СМЕНА СЛОЯ: %d =====" % new_layer)
    def _schedule_pause_and_resume(self, wait_time):
        def _async_action(eventtime):
            try:
                if not self.is_printing or not self.enabled:
                    return
                self._log(1, "Инициирую PAUSE...")
                self.gcode.run_script_from_command("M118 Система контроли времени слоя - Ожидание")
                self.gcode.run_script_from_command("PAUSE")
                self.gcode.run_script_from_command("Ожидание %.1f секунд..." % wait_time)
                self._log(1, "Ожидание %.1f секунд..." % wait_time)
                self.reactor.pause(self.reactor.monotonic() + wait_time)
                if self.is_printing and self.enabled:
                    self._log(1, "Инициирую RESUME...")
                    self.gcode.run_script_from_command("RESUME")
                else:
                    self._log(1, "Печать отменена или контроль выключен во время ожидания")
            except Exception as e:
                self._log(0, "Ошибка в _schedule_pause_and_resume: %s" % str(e))
        self.reactor.register_callback(_async_action)
    def _status_update(self, eventtime):
        """Периодическая проверка состояния"""
        try:
            # Проверяем активность печати
            if self.is_printing and self.enabled and self.current_layer > 0:
                # Если слой идет слишком долго (более 5 минут) - сбрасываем
                elapsed = eventtime - self.layer_start_time
                if elapsed > 300:  # 5 минут
                    self._log(2, "Слой %d длится слишком долго (%.0f сек), сброс" % (self.current_layer, elapsed))
                    self.layer_start_time = eventtime
                    self.last_layer_time = 0
                else:
                    self._log(3, "Статус: слой %d, время: %.1f/%.1f сек" % (
                        self.current_layer, elapsed, self.min_layer_time))
        except Exception as e:
            self._log(0, "Ошибка в status_update: %s" % str(e))
        return eventtime + 5.0  # Проверка каждые 5 секунд
    def cmd_ENABLE(self, gcmd):
        """Включение контроля времени слоя"""
        self.enabled = True
        gcmd.respond_info("Контроль времени слоя ВКЛЮЧЕН")
        self._log(1, "Контроль времени слоя ВКЛЮЧЕН")
    def cmd_DISABLE(self, gcmd):
        """Выключение контроля времени слоя"""
        self.enabled = False
        gcmd.respond_info("Контроль времени слоя ВЫКЛЮЧЕН")
        self._log(1, "Контроль времени слоя ВЫКЛЮЧЕН")
    def _log(self, level, message):
        """Логирование с учетом уровня отладки"""
        if self.debug_level >= level:
            self.logger.info(message)

def load_config(config):
    return MinLayerTimer(config)