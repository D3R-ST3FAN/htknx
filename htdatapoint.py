#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" TODO """

import logging

from xknx.devices import Device
from xknx.remote_value.remote_value_sensor import RemoteValueSensor
from xknx.remote_value.remote_value_switch import RemoteValueSwitch

from typing import Union

# from ??? import ht_heatpump  # type: ignore


_LOGGER = logging.getLogger(__name__)


class HtDataPoint(Device):
    """Representation of a Heliotherm heat pump parameter."""

    def __init__(
        self,
        xknx,
        name: str,
        group_address,
        value_type: str,
        writable: bool = False,
        cyclic_sending: bool = False,
        send_on_change: bool = False,
        on_change_of: Union[None, int, float] = None,
        device_updated_cb=None,
    ):
        """Initialize HtDataPoint class."""
        super().__init__(xknx, name, device_updated_cb)

        self.param_value = None
        if value_type == "binary":
            self.param_value = RemoteValueSwitch(
                xknx,
                group_address=group_address,
                sync_state=False,
                device_name=self.name,
                after_update_cb=self.after_update,
            )
        else:
            self.param_value = RemoteValueSensor(
                xknx,
                group_address=group_address,
                sync_state=False,
                device_name=self.name,
                after_update_cb=self.after_update,
                value_type=value_type,
            )
        self.writable = writable
        self.cyclic_sending = cyclic_sending
        self.send_on_change = send_on_change
        self.on_change_of = on_change_of
        self.last_sent_value: Union[None, bool, int, float] = None

    def _iter_remote_values(self):
        """Iterate the devices RemoteValue classes."""
        yield self.param_value

    @classmethod
    def from_config(cls, xknx, name, config, device_updated_cb=None):
        """Initialize object from configuration structure."""
        group_address = config.get("group_address")
        value_type = config.get("value_type")
        writable = config.get("writable")
        cyclic_sending = config.get("cyclic_sending")
        send_on_change = config.get("send_on_chnage")
        on_change_of = config.get("on_change_of")

        return cls(
            xknx,
            name,
            group_address=group_address,
            value_type=value_type,
            writable=writable,
            cyclic_sending=cyclic_sending,
            send_on_change=send_on_change,
            on_change_of=on_change_of,
            device_updated_cb=device_updated_cb,
        )

    async def broadcast_value(self, response=False):
        """Broadcast parameter value to KNX bus."""
        if response or self.cyclic_sending:
            value = self.param_value.value
            value = (
                True if isinstance(self.param_value, RemoteValueSwitch) else 123
            )  # TODO remove!
            if value is None:
                return
            await self.param_value.set(value, response=response)

    async def process_group_read(self, telegram):
        """Process incoming GROUP READ telegram."""
        _LOGGER.info("HtDataPoint.process_group_read: %s", telegram)
        await self.broadcast_value(True)

    async def process_group_write(self, telegram):
        """Process incoming GROUP WRITE telegram."""
        _LOGGER.info("HtDataPoint.process_group_write: %s", telegram)
        if await self.param_value.process(telegram):
            value = self.param_value.value
            if not self.writable:
                _LOGGER.warning(
                    "Attempted to set value for non-writable heat pump parameter: '%s' (value: %s)",
                    self.name,
                    value,
                )
                return
            # TODO ht_heatpump.set_param_async() in try-block
            _LOGGER.info(
                "HtDataPoint.process_group_write: ht_heatpump.set_param_async('%s', %s)",
                self.name,
                value,
            )
            # value = await ht_heatpump.set_param_async(self.name, value)
            self.param_value.payload = self.param_value.to_knx(value)

    async def set(self, value):
        """Set new value and send it to the KNX bus, if desired."""
        if value is None:
            return
        # TODO on_change_of_relative / on_change_of_absolute
        if (
            isinstance(self.param_value, RemoteValueSwitch)
            and value != self.param_value.value
        ):
            if self.send_on_change:
                await self.param_value.set(value)
                self.last_sent_value = value
            else:
                self.param_value.payload = self.param_value.to_knx(value)
        elif (
            isinstance(self.param_value, RemoteValueSensor)
            and value != self.param_value.value
        ):
            if self.send_on_change and (
                self.on_change_of is None
                or self.last_sent_value is None
                or abs(value - self.last_sent_value) >= abs(self.on_change_of)
            ):
                await self.param_value.set(value)
                self.last_sent_value = value
            else:
                self.param_value.payload = self.param_value.to_knx(value)

    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self.param_value.unit_of_measurement

    def resolve_state(self):
        """Return the current state of the heat pump parameter as a human readable string."""
        return self.param_value.value

    def __str__(self):
        """Return object as readable string."""
        return (
            '<HtDataPoint name="{}" group_address="{}" value_type="{}" value="{}" unit="{}"'
            ' writable="{}" cyclic_sending="{}" send_on_change="{}" on_change_of="{}"/>'
        ).format(
            self.name,
            self.param_value.group_address,
            "binary"
            if isinstance(self.param_value, RemoteValueSwitch)
            else self.param_value.dpt_class.value_type,
            self.resolve_state(),
            self.unit_of_measurement(),
            "yes" if self.writable else "no",
            "yes" if self.cyclic_sending else "no",
            "yes" if self.send_on_change else "no",
            self.on_change_of,
        )
