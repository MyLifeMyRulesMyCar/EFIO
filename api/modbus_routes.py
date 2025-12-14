from flask import Blueprint, jsonify, request
from efio_daemon.modbus_manager import modbus_manager
from efio_daemon.state import state

modbus_api = Blueprint("modbus_api", __name__)

@modbus_api.route("/api/modbus/connect", methods=["POST"])
def connect():
    slave = int(request.json.get("slave", 1))
    ok = modbus_manager.connect(slave)
    state["modbus"]["slave_id"] = slave
    return jsonify({"connected": ok})

@modbus_api.route("/api/modbus/read/<reg>", methods=["GET"])
def read_register(reg):
    reg = int(reg)
    value = modbus_manager.read_register(reg)
    state["modbus"]["last_register"] = reg
    state["modbus"]["last_value"] = value
    return jsonify({
        "register": reg,
        "value": value
    })
