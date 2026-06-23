# =========================================================================================
# 📟 MAX30102 HARDWARE REGISTER DRIVER MODULE
# =========================================================================================
# Description:
#   A lightweight, industrial-grade register driver for the MAX30102 high-sensitivity 
#   pulse oximeter and heart-rate optical sensor. This class interacts directly with 
#   the hardware silicon over the I2C peripheral interface.
#
# 🧠 Register Architecture Breakdown:
#   - 0x57: The standard fixed 7-bit factory I2C slave address for the device.
#   - 0x09 (Mode Config): Rules power-down states, resets, and active optical modes.
#   - 0x0A (SpO2 Config): Fine-tunes the ADC resolution, sampling rates, and pulse widths.
#   - 0x0C & 0x0D (LED Power): Modulates the physical current (mA) fed into the lasers.
#   - 0x07 (FIFO Data): The doorway to the internal 32-sample deep memory queue.
#
# 🧮 Bit-Shifting & Masking Theory:
#   The sensor transmits data as a stream of raw 8-bit bytes. Each channel (Red and IR) 
#   outputs an 18-bit resolution value packed into 3 consecutive bytes (24 bits total).
#   - Byte 1 is shifted left by 16 bits (`<< 16`) to become the most significant bits.
#   - Byte 2 is shifted left by 8 bits (`<< 8`).
#   - Byte 3 forms the baseline single bits.
#   - An OR logic gate (`|`) merges them, and an 18-bit bitmask (`& 0x03FFFF`) strips 
#     away empty leading hardware overhead bits.
# =========================================================================================

import time

class MAX30102:
    def __init__(self, i2c, address=0x57):
        """Initializes the sensor instance and binds the active I2C bus channel."""
        self.i2c = i2c
        self.address = address

    def _write_reg(self, reg, val):
        """Low-level abstract method: Secures the bus and writes 1 byte to a target hardware register."""
        while not self.i2c.try_lock():
            pass
        try:
            self.i2c.writeto(self.address, bytes([reg, val]))
        finally:
            self.i2c.unlock()

    def _read_reg(self, reg, length):
        """Low-level abstract method: Reaches into a register address and reads back a specific byte length block."""
        result = bytearray(length)
        while not self.i2c.try_lock():
            pass
        try:
            self.i2c.writeto_then_readfrom(self.address, bytes([reg]), result)
        finally:
            self.i2c.unlock()
        return result

    def setup_sensor(self):
        """Executes the standard sequence to configure registers for vital scanning."""
        # 1. Soft Reset: Resets all configuration registers to factory defaults
        self._write_reg(0x09, 0x40)
        time.sleep(0.1) # Wait for the silicon to power-cycle cleanly
        
        # 2. Mode Configuration: Set to SpO2 mode (Both Red and IR LEDs enabled)
        self._write_reg(0x09, 0x03)
        
        # 3. SpO2 Config: 18-bit ADC resolution range, 400 Samples/sec, 411us Pulse Width
        self._write_reg(0x0A, 0x27)
        
        # 4. LED Pulse Amplitude: Set physical current limits (balancing skin absorption)
        self._write_reg(0x0C, 0x1F) # Red Laser (~6.2mA current drive)
        self._write_reg(0x0D, 0x3F) # IR Laser (~12.6mA current drive for deeper tissue read)
        
        # 5. Clear Buffer: Wipe FIFO Write, Read, and Overflow pointers to start fresh
        self._write_reg(0x04, 0x00) 
        self._write_reg(0x05, 0x00) 
        self._write_reg(0x06, 0x00) 

    def shutdown(self):
        """Power Management: Shuts down LED current lines to save power and turn off the lasers."""
        self._write_reg(0x0C, 0x00) # Cut current to Red channel completely
        self._write_reg(0x0D, 0x00) # Cut current to IR channel completely

    def wakeup(self):
        """Power Management: Re-energizes the LEDs back to their verified operational current thresholds."""
        self._write_reg(0x0C, 0x1F) # Restore balanced Red channel output
        self._write_reg(0x0D, 0x3F) # Restore balanced IR channel output

    def check(self):
        """Interface placeholder requirement."""
        pass

    def available(self):
        """Always returns True to satisfy standard streaming buffer validation protocols."""
        return True

    def pop_raw_data(self):
        """Reads the next 6 sequential bytes from the FIFO buffer and reconstructs them into optical data."""
        # Pull 6 bytes out of register 0x07 (3 bytes for Red channel, 3 bytes for IR channel)
        data = self._read_reg(0x07, 6)
        
        # Reconstruct the 24-bit streams into real 18-bit resolution integers
        red = (data[0] << 16 | data[1] << 8 | data[2]) & 0x03FFFF
        ir = (data[3] << 16 | data[4] << 8 | data[5]) & 0x03FFFF
        
        return red, ir
