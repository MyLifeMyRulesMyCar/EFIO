#!/usr/bin/env python3
# check_memory.py - Analyze memory usage of EFIO application

import psutil
import os

def bytes_to_mb(bytes_val):
    return round(bytes_val / (1024 * 1024), 2)

def check_efio_memory():
    """Check memory usage of EFIO-related processes"""
    
    print("=" * 60)
    print("EFIO Application Memory Analysis")
    print("=" * 60)
    
    # Overall system memory
    mem = psutil.virtual_memory()
    print(f"\n📊 System Memory Overview:")
    print(f"   Total:     {bytes_to_mb(mem.total)} MB")
    print(f"   Used:      {bytes_to_mb(mem.used)} MB ({mem.percent}%)")
    print(f"   Available: {bytes_to_mb(mem.available)} MB")
    print(f"   Free:      {bytes_to_mb(mem.free)} MB")
    
    # Find EFIO processes
    efio_processes = []
    other_python = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info']):
        try:
            pinfo = proc.info
            cmdline = ' '.join(pinfo['cmdline']) if pinfo['cmdline'] else ''
            
            if 'python' in pinfo['name'].lower():
                mem_mb = bytes_to_mb(pinfo['memory_info'].rss)
                
                if 'efio' in cmdline.lower() or 'app.py' in cmdline.lower():
                    efio_processes.append({
                        'pid': pinfo['pid'],
                        'name': pinfo['name'],
                        'cmd': cmdline[:80],
                        'memory_mb': mem_mb
                    })
                else:
                    other_python.append({
                        'pid': pinfo['pid'],
                        'name': pinfo['name'],
                        'cmd': cmdline[:80],
                        'memory_mb': mem_mb
                    })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    # Report EFIO processes
    print(f"\n🐍 EFIO Application Processes:")
    if efio_processes:
        total_efio_mem = 0
        for proc in efio_processes:
            print(f"   PID {proc['pid']}: {proc['memory_mb']} MB")
            print(f"      {proc['cmd']}")
            total_efio_mem += proc['memory_mb']
        print(f"\n   ✅ Total EFIO Memory: {total_efio_mem} MB")
        print(f"   📊 Percentage of Total: {round(total_efio_mem / bytes_to_mb(mem.total) * 100, 2)}%")
    else:
        print("   ⚠️  No EFIO processes found")
    
    # Report other Python processes
    if other_python:
        print(f"\n🐍 Other Python Processes:")
        for proc in other_python:
            print(f"   PID {proc['pid']}: {proc['memory_mb']} MB - {proc['cmd']}")
    
    # Top 10 memory consumers
    print(f"\n🔝 Top 10 Memory Consumers:")
    all_procs = []
    for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
        try:
            pinfo = proc.info
            all_procs.append({
                'pid': pinfo['pid'],
                'name': pinfo['name'],
                'memory_mb': bytes_to_mb(pinfo['memory_info'].rss)
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    all_procs.sort(key=lambda x: x['memory_mb'], reverse=True)
    
    for i, proc in enumerate(all_procs[:10], 1):
        print(f"   {i}. {proc['name']:<20} - {proc['memory_mb']:>8} MB (PID {proc['pid']})")
    
    # Analysis
    print(f"\n📋 Analysis:")
    if efio_processes:
        total_efio_mem = sum(p['memory_mb'] for p in efio_processes)
        if total_efio_mem < 100:
            print(f"   ✅ EFIO app using {total_efio_mem} MB - This is NORMAL and GOOD")
        elif total_efio_mem < 200:
            print(f"   ⚠️  EFIO app using {total_efio_mem} MB - Slightly high but acceptable")
        else:
            print(f"   ❌ EFIO app using {total_efio_mem} MB - This is HIGH, may have memory leak")
    
    if mem.percent > 80:
        print(f"   ⚠️  Overall system memory at {mem.percent}% - Consider:")
        print(f"      • Disabling unused services")
        print(f"      • Not running desktop environment")
        print(f"      • Adding swap if needed")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    check_efio_memory()