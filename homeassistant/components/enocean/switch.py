"""Support for EnOcean switches."""
import voluptuous as vol
from enocean.protocol.constants import RORG
from enocean.protocol.packet import RadioPacket


from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import CONF_ID, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import ToggleEntity

from .device import EnOceanEntity
from .const import SWITCH_ALL_CHANNELS

CONF_CHANNEL = "channel"
CONF_SENDER_ID = "sender_id"
DEFAULT_NAME = "EnOcean Switch"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_CHANNEL, default=SWITCH_ALL_CHANNELS): vol.All(
            int, vol.Range(min=0, max=31)
        ),  # Default all channels
        vol.Required(CONF_SENDER_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the EnOcean switch platform."""
    channel = config.get(CONF_CHANNEL)
    dev_id = config.get(CONF_ID)
    dev_name = config.get(CONF_NAME)
    sender_id = config.get(CONF_SENDER_ID)

    add_entities([EnOceanSwitch(dev_id, dev_name, channel, sender_id)])


class EnOceanSwitch(EnOceanEntity, ToggleEntity):
    """Representation of an EnOcean switch device."""

    def __init__(self, dev_id, dev_name, channel, sender_id):
        """Initialize the EnOcean switch device."""
        super().__init__(dev_id, dev_name)
        self._light = None
        self._on_state = False
        self._on_state2 = False
        self.channel = channel
        self.sender_id = sender_id

    @property
    def is_on(self):
        """Return whether the switch is on or off."""
        return self._on_state

    @property
    def name(self):
        """Return the device name."""
        return self.dev_name

    def turn_on(self, **kwargs):
        """"Turn on the switch."""
        packet = RadioPacket.create(
            rorg=RORG.VLD,
            rorg_func=0x01,
            rorg_type=0x01,
            sender=self.sender_id,
            destination=self.dev_id,
            command=1,  # Change actuator
            DV=0,  # Switch to new output value (no dimming value)
            IO=self.channel,  # The configured channel
            OV=0x64,  # ON (or 100%)
        )
        self.send_packet(packet)
        self._on_state = True

    def turn_off(self, **kwargs):
        """Turn off the switch."""
        packet = RadioPacket.create(
            rorg=RORG.VLD,
            rorg_func=0x01,
            rorg_type=0x01,
            sender=self.sender_id,
            destination=self.dev_id,
            command=1,  # Change actuator
            DV=0,  # Switch to new output value (no dimming value)
            IO=0x1E,  # The configured channel
            OV=0x0,  # OF (or 0%)
        )
        self.send_packet(packet)
        self._on_state = False

    def value_changed(self, packet):
        """Update the internal state of the switch."""
        if packet.data[0] == 0xA5:
            # power meter telegram, turn on if > 10 watts
            packet.parse_eep(0x12, 0x01)
            if packet.parsed["DT"]["raw_value"] == 1:
                raw_val = packet.parsed["MR"]["raw_value"]
                divisor = packet.parsed["DIV"]["raw_value"]
                watts = raw_val / (10 ** divisor)
                if watts > 1:
                    self._on_state = True
                    self.schedule_update_ha_state()
        elif packet.data[0] == 0xD2:
            # actuator status telegram
            packet.parse_eep(0x01, 0x01)
            if packet.parsed["CMD"]["raw_value"] == 4:
                channel = packet.parsed["IO"]["raw_value"]
                output = packet.parsed["OV"]["raw_value"]
                if (
                    channel == self.channel or self.channel == SWITCH_ALL_CHANNELS
                ):  # my channel or all channels
                    self._on_state = output > 0
                    self.schedule_update_ha_state()
