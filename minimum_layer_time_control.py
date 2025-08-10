# Контроль минимального времени слоя
#
# This file may be distributed under the terms of the GNU GPLv3 license.

import logging
from . import idle_timeout

class MinLayerTimer:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object('gcode')
        # Параметр конфигурации
        self.min_layer_time = config.getfloat('min_layer_time', 20.0)
        # Состояние печати
        self.is_printing = False
        self.current_layer = None
        self.layer_start_time = None
        # Регистрация обработчиков событий
        self.printer.register_event_handler("idle_timeout:printing",
                                          self.handle_printing_start)
        self.printer.register_event_handler("idle_timeout:ready",
                                          self.handle_printing_end)
        self.printer.register_event_handler("gcode:layer",
                                          self.handle_layer_change)
        # Регистрация команды
        self.gcode.register_command(
            "SET_MIN_LAYER_TIME",
            self.cmd_SET_MIN_LAYER_TIME,
            desc=self.cmd_SET_MIN_LAYER_TIME_help)
    cmd_SET_MIN_LAYER_TIME_help = "Установка минимального времени слоя"
    def cmd_SET_MIN_LAYER_TIME(self, gcmd):
        time = gcmd.get_float('TIME', self.min_layer_time)
        if time < 0.1:
            raise gcmd.error("Время слоя должно быть больше 0.1 секунды")
        self.min_layer_time = time
        gcmd.respond_info("Минимальное время слоя установлено: %.1f секунд" % time)
    def handle_printing_start(self, print_time):
        self.is_printing = True
        self.current_layer = None
        self.layer_start_time = None
    def handle_printing_end(self, print_time):
        self.is_printing = False
        self.current_layer = None
        self.layer_start_time = None
    def handle_layer_change(self, new_layer):
        if not self.is_printing:
            return
        current_time = self.reactor.monotonic()
        # Проверяем длительность предыдущего слоя
        if self.layer_start_time is not None:
            layer_duration = current_time - self.layer_start_time
            if layer_duration < self.min_layer_time:
                wait_time = self.min_layer_time - layer_duration
                self._schedule_pause_and_resume(wait_time)
        # Обновляем состояние для нового слоя
        self.current_layer = new_layer
        self.layer_start_time = current_time
    def _schedule_pause_and_resume(self, wait_time):
        def _async_action(eventtime):
            if not self.is_printing:
                return
            try:
                # Ставим на паузу
                self.gcode.run_script_from_command("PAUSE")
                # Ждем указанное время
                self.reactor.pause(self.reactor.monotonic() + wait_time)
                # Возобновляем печать
                if self.is_printing:
                    self.gcode.run_script_from_command("RESUME")
            except Exception:
                logging.exception("Ошибка в контроле времени слоя")
        self.reactor.register_callback(_async_action)

def load_config(config):
    return MinLayerTimer(config)