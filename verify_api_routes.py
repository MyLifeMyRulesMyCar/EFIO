#!/usr/bin/env python3
# verify_api_routes.py
# Check if CAN-MQTT bridge routes are registered

import sys
sys.path.insert(0, '/home/radxa/efio')

print("=" * 60)
print("API Routes Verification")
print("=" * 60)

try:
    from api.app import app
    
    print("\n✅ Successfully imported Flask app")
    
    # Get all registered routes
    print("\n📋 All Registered Routes:")
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            'endpoint': rule.endpoint,
            'methods': ','.join(rule.methods - {'HEAD', 'OPTIONS'}),
            'path': str(rule)
        })
    
    # Sort by path
    routes.sort(key=lambda x: x['path'])
    
    # Check for CAN-MQTT routes
    can_mqtt_routes = [r for r in routes if 'can-mqtt' in r['path']]
    
    if can_mqtt_routes:
        print(f"\n✅ Found {len(can_mqtt_routes)} CAN-MQTT Bridge routes:")
        for route in can_mqtt_routes:
            print(f"   {route['methods']:12} {route['path']}")
    else:
        print("\n❌ No CAN-MQTT Bridge routes found!")
        print("\nPossible issues:")
        print("1. Blueprint not registered in app.py")
        print("2. Import error in can_mqtt_routes.py")
        print("3. Routes not defined correctly")
    
    # Show some other routes for context
    print(f"\n📌 Total routes registered: {len(routes)}")
    print("\nSample of other routes:")
    for route in routes[:10]:
        if 'can-mqtt' not in route['path']:
            print(f"   {route['methods']:12} {route['path']}")
    
    # Check if bridge instance is set
    print("\n🔍 Checking bridge instance:")
    try:
        from api.can_mqtt_routes import bridge_instance
        if bridge_instance:
            print(f"   ✅ Bridge instance: {bridge_instance}")
        else:
            print(f"   ⚠️  Bridge instance is None")
            print(f"   This is OK if init hasn't run yet")
    except ImportError as e:
        print(f"   ❌ Cannot import can_mqtt_routes: {e}")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)

# Test if routes respond
print("\n🧪 Testing Route Accessibility:")
print("Run these commands to test:")
print("")
print("# Test status endpoint:")
print("curl http://localhost:5000/api/can-mqtt/status \\")
print("  -H 'Authorization: Bearer YOUR_TOKEN'")
print("")
print("# Test mappings endpoint:")
print("curl http://localhost:5000/api/can-mqtt/mappings \\")
print("  -H 'Authorization: Bearer YOUR_TOKEN'")
print("")
print("=" * 60)