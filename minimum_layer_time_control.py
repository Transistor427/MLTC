# This file may be distributed under the terms of the GNU GPLv3 license.

import logging

class MinLayerTimer:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object('gcode')
        self.min_layer_time = config.getfloat('min_layer_time', 20.0, above=0.)
        self.enabled = False
        self.is_printing = False
        self.current_layer = 0
        self.layer_start_time = 0.
        self.last_layer_time = 0.
        self.status_timer = None
        self._prev_M117 = None
        self._prev_SET_PRINT_STATS_INFO = None
        self.logger = logging.getLogger('min_layer_timer')
        self.printer.register_event_handler("klippy:connect", self._handle_connect)
        self.printer.register_event_handler("klippy:started", self._handle_started)
        self.printer.register_event_handler("klippy:disconnect", self._handle_disconnect)
        self.printer.register_event_handler("idle_timeout:printing",
                                          self._handle_printing_start)
        self.printer.register_event_handler("idle_timeout:ready",
                                          self._handle_printing_end)
        self.printer.register_event_handler("idle_timeout:idle",
                                          self._handle_printing_end)
        self.gcode.register_command(
            'MINIMUM_LAYER_TIME_CONTROL_ENABLE',
            self.cmd_ENABLE,
            desc="Enable minimum layer time control")
        self.gcode.register_command(
            'MINIMUM_LAYER_TIME_CONTROL_DISABLE',
            self.cmd_DISABLE,
            desc="Disable minimum layer time control")
        self.gcode.register_command(
            'MINIMUM_LAYER_TIME_CONTROL_LAYER',
            self.cmd_LAYER,
            desc="Notify layer change for minimum layer time control")

    def _handle_connect(self):
        # Wrap after other modules register their handlers
        self._prev_M117 = self.gcode.register_command('M117', None)
        self.gcode.register_command('M117', self.cmd_M117)
        self._prev_SET_PRINT_STATS_INFO = self.gcode.register_command(
            'SET_PRINT_STATS_INFO', None)
        self.gcode.register_command('SET_PRINT_STATS_INFO',
                                    self.cmd_SET_PRINT_STATS_INFO)

    def _handle_started(self):
        self.status_timer = self.reactor.register_timer(
            self._status_update, self.reactor.NOW)

    def _handle_disconnect(self):
        if self.status_timer is not None:
            self.reactor.unregister_timer(self.status_timer)
            self.status_timer = None

    def _handle_printing_start(self, print_time):
        self.is_printing = True
        self.current_layer = 0
        self.layer_start_time = self.reactor.monotonic()
        self.last_layer_time = 0.

    def _handle_printing_end(self, print_time):
        self.is_printing = False

    def cmd_SET_PRINT_STATS_INFO(self, gcmd):
        if gcmd.get('CURRENT_LAYER', None) is not None:
            try:
                self._handle_layer_change(int(gcmd.get('CURRENT_LAYER')))
            except ValueError:
                pass
        if self._prev_SET_PRINT_STATS_INFO is not None:
            self._prev_SET_PRINT_STATS_INFO(gcmd)

    def cmd_M117(self, gcmd):
        msg = gcmd.get_commandline()
        if "LAYER:" in msg:
            try:
                parts = msg.split("LAYER:")
                if len(parts) > 1:
                    self._handle_layer_change(int(parts[1].strip().split()[0]))
            except ValueError:
                pass
        if self._prev_M117 is not None:
            self._prev_M117(gcmd)

    def _handle_layer_change(self, new_layer):
        if not self.is_printing or not self.enabled:
            return
        if new_layer == self.current_layer:
            return
        current_time = self.reactor.monotonic()
        if self.current_layer > 0 and self.layer_start_time > 0.:
            self.last_layer_time = current_time - self.layer_start_time
            if self.last_layer_time < self.min_layer_time:
                wait_time = self.min_layer_time - self.last_layer_time
                self._schedule_pause_and_resume(wait_time)
        self.current_layer = new_layer
        self.layer_start_time = current_time

    def _schedule_pause_and_resume(self, wait_time):
        def _async_action(eventtime):
            try:
                if not self.is_printing or not self.enabled:
                    return
                self.gcode.respond_info(
                    "Контроль времени слоя: пауза %.1f с" % wait_time)
                self.gcode.run_script_from_command("PAUSE")
                self.reactor.pause(self.reactor.monotonic() + wait_time)
                if self.is_printing and self.enabled:
                    self.gcode.run_script_from_command("RESUME")
                else:
                    self.gcode.respond_info(
                        "Контроль времени слоя: ожидание прервано")
            except Exception as e:
                self.logger.exception("pause/resume failed: %s", e)
                self.gcode.respond_info(
                    "Контроль времени слоя: ошибка паузы")
        self.reactor.register_callback(_async_action)

    def _status_update(self, eventtime):
        # Reset stuck layer timer after 5 minutes without a layer change
        if self.is_printing and self.enabled and self.current_layer > 0:
            elapsed = eventtime - self.layer_start_time
            if elapsed > 300.:
                self.layer_start_time = eventtime
                self.last_layer_time = 0.
        return eventtime + 30.

    def cmd_LAYER(self, gcmd):
        layer = gcmd.get_int('LAYER', None)
        if layer is None:
            layer = gcmd.get_int('NUM_LAYER', None)
        if layer is None:
            raise gcmd.error("LAYER or NUM_LAYER is required")
        self._handle_layer_change(layer)

    def cmd_ENABLE(self, gcmd):
        self.enabled = True
        gcmd.respond_info("Контроль времени слоя активирован")

    def cmd_DISABLE(self, gcmd):
        self.enabled = False
        gcmd.respond_info("Контроль времени слоя отключен")

def load_config(config):
    return MinLayerTimer(config)
