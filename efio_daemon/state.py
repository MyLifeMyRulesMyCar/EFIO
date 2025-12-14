# Shared I/O state for the whole system

state = {
    "di": [0, 0, 0, 0],   # 4 digital inputs
    "do": [0, 0, 0, 0],   # 4 digital outputs
    "simulation": False ,   # set False when real hardware connected
    "simulation_oled": False ,  

    "modbus": {
        "slave_id": 1,
        "last_register": None,
        "last_value": None
    }
}


