#!/usr/bin/env python3
"""
EFIO Edge Controller - Backup/Restore Utility
Backs up and restores configuration, users, and device data
"""

import os
import sys
import json
import shutil
import tarfile
import argparse
from datetime import datetime
from pathlib import Path

# Configuration
CONFIG_DIR = Path.home() / "efio"
BACKUP_DIR = Path.home() / "efio_backups"
DEFAULT_BACKUP_NAME = f"efio_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.tar.gz"

# Files to backup
BACKUP_FILES = [
    "users.json",
    "network_config.json",
    "io_config.json",
    "alarm_config.json",
    "modbus_devices.json",
    "modbus_log.json",
    "pairing.json"
]

class Colors:
    """ANSI color codes"""
    GREEN = '\033[0;32m'
    BLUE = '\033[0;34m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    NC = '\033[0m'  # No Color

def print_success(msg):
    print(f"{Colors.GREEN}✓ {msg}{Colors.NC}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ {msg}{Colors.NC}")

def print_warning(msg):
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.NC}")

def print_error(msg):
    print(f"{Colors.RED}✗ {msg}{Colors.NC}")

def print_header(msg):
    print(f"\n{Colors.BLUE}{'='*50}{Colors.NC}")
    print(f"{Colors.BLUE}{msg}{Colors.NC}")
    print(f"{Colors.BLUE}{'='*50}{Colors.NC}\n")

def ensure_dirs():
    """Ensure config and backup directories exist"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

def list_config_files():
    """List all configuration files"""
    files = []
    for filename in BACKUP_FILES:
        filepath = CONFIG_DIR / filename
        if filepath.exists():
            size = filepath.stat().st_size
            mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
            files.append({
                'name': filename,
                'path': filepath,
                'size': size,
                'modified': mtime
            })
    return files

def create_backup(output_path=None, include_logs=False):
    """Create backup archive of configuration files"""
    print_header("Creating Backup")
    
    ensure_dirs()
    
    # Determine output path
    if output_path is None:
        output_path = BACKUP_DIR / DEFAULT_BACKUP_NAME
    else:
        output_path = Path(output_path)
    
    # Get files to backup
    files = list_config_files()
    
    if not files:
        print_warning("No configuration files found to backup")
        return False
    
    print_info(f"Found {len(files)} configuration files")
    
    # Create backup archive
    try:
        with tarfile.open(output_path, "w:gz") as tar:
            for file_info in files:
                # Skip logs unless requested
                if 'log' in file_info['name'].lower() and not include_logs:
                    print_info(f"Skipping log file: {file_info['name']}")
                    continue
                
                print_info(f"Adding: {file_info['name']} ({file_info['size']} bytes)")
                tar.add(file_info['path'], arcname=file_info['name'])
            
            # Add metadata
            metadata = {
                'created': datetime.now().isoformat(),
                'hostname': os.uname().nodename,
                'version': '1.0.0',
                'files': [f['name'] for f in files]
            }
            
            # Create metadata file
            metadata_path = CONFIG_DIR / "backup_metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            tar.add(metadata_path, arcname="backup_metadata.json")
            
            # Clean up metadata file
            metadata_path.unlink()
        
        # Get backup size
        backup_size = output_path.stat().st_size
        
        print_success(f"Backup created: {output_path}")
        print_info(f"Backup size: {backup_size / 1024:.1f} KB")
        
        return True
        
    except Exception as e:
        print_error(f"Backup failed: {e}")
        return False

def restore_backup(backup_path, force=False):
    """Restore configuration from backup archive"""
    print_header("Restoring Backup")
    
    ensure_dirs()
    
    backup_path = Path(backup_path)
    
    if not backup_path.exists():
        print_error(f"Backup file not found: {backup_path}")
        return False
    
    print_info(f"Backup file: {backup_path}")
    
    # Extract and validate backup
    try:
        with tarfile.open(backup_path, "r:gz") as tar:
            members = tar.getmembers()
            
            print_info(f"Backup contains {len(members)} files")
            
            # Check for metadata
            metadata = None
            for member in members:
                if member.name == "backup_metadata.json":
                    f = tar.extractfile(member)
                    metadata = json.load(f)
                    break
            
            if metadata:
                print_info(f"Backup created: {metadata['created']}")
                print_info(f"From host: {metadata['hostname']}")
            
            # Confirm restoration
            if not force:
                print_warning("This will overwrite existing configuration files!")
                response = input("Continue with restore? (yes/no): ").strip().lower()
                if response not in ['yes', 'y']:
                    print_info("Restore cancelled")
                    return False
            
            # Create backup of current config before restore
            current_backup = BACKUP_DIR / f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.tar.gz"
            print_info(f"Creating safety backup: {current_backup}")
            create_backup(current_backup, include_logs=False)
            
            # Extract files
            print_info("Extracting files...")
            for member in members:
                if member.name == "backup_metadata.json":
                    continue
                
                print_info(f"Restoring: {member.name}")
                tar.extract(member, path=CONFIG_DIR)
            
            print_success("Backup restored successfully")
            print_warning("You may need to restart the EFIO service for changes to take effect")
            print_info("Restart command: sudo systemctl restart efio-api")
            
            return True
            
    except Exception as e:
        print_error(f"Restore failed: {e}")
        return False

def list_backups():
    """List all available backups"""
    print_header("Available Backups")
    
    ensure_dirs()
    
    backups = sorted(BACKUP_DIR.glob("*.tar.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
    
    if not backups:
        print_info("No backups found")
        return []
    
    print(f"{'Name':<40} {'Size':>10} {'Created':<20}")
    print("-" * 72)
    
    for backup in backups:
        size = backup.stat().st_size / 1024  # KB
        mtime = datetime.fromtimestamp(backup.stat().st_mtime)
        print(f"{backup.name:<40} {size:>8.1f} KB {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
    
    return backups

def show_config_status():
    """Show current configuration status"""
    print_header("Configuration Status")
    
    ensure_dirs()
    
    files = list_config_files()
    
    if not files:
        print_warning("No configuration files found")
        return
    
    print(f"{'File':<30} {'Size':>10} {'Last Modified':<20}")
    print("-" * 62)
    
    for file_info in files:
        size = file_info['size']
        mtime = file_info['modified'].strftime('%Y-%m-%d %H:%M:%S')
        print(f"{file_info['name']:<30} {size:>8} B {mtime}")
    
    print(f"\nTotal files: {len(files)}")
    print(f"Config directory: {CONFIG_DIR}")

def export_config_json(output_path=None):
    """Export all configuration as a single JSON file"""
    print_header("Exporting Configuration")
    
    ensure_dirs()
    
    if output_path is None:
        output_path = f"efio_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    config = {
        'metadata': {
            'exported': datetime.now().isoformat(),
            'hostname': os.uname().nodename,
            'version': '1.0.0'
        },
        'configuration': {}
    }
    
    # Load all config files
    for filename in BACKUP_FILES:
        filepath = CONFIG_DIR / filename
        if filepath.exists():
            try:
                with open(filepath, 'r') as f:
                    config['configuration'][filename] = json.load(f)
                print_info(f"Loaded: {filename}")
            except Exception as e:
                print_warning(f"Could not load {filename}: {e}")
    
    # Save combined config
    try:
        with open(output_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        file_size = Path(output_path).stat().st_size
        print_success(f"Configuration exported: {output_path}")
        print_info(f"File size: {file_size / 1024:.1f} KB")
        return True
        
    except Exception as e:
        print_error(f"Export failed: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description='EFIO Configuration Backup/Restore Utility',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create backup
  ./backup_restore.py backup
  
  # Create backup with logs
  ./backup_restore.py backup --include-logs
  
  # Restore from backup
  ./backup_restore.py restore efio_backup_20241223_120000.tar.gz
  
  # List available backups
  ./backup_restore.py list
  
  # Show current configuration status
  ./backup_restore.py status
  
  # Export configuration as JSON
  ./backup_restore.py export
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Backup command
    backup_parser = subparsers.add_parser('backup', help='Create configuration backup')
    backup_parser.add_argument('-o', '--output', help='Output path for backup file')
    backup_parser.add_argument('--include-logs', action='store_true', help='Include log files in backup')
    
    # Restore command
    restore_parser = subparsers.add_parser('restore', help='Restore configuration from backup')
    restore_parser.add_argument('backup_file', help='Path to backup file')
    restore_parser.add_argument('-f', '--force', action='store_true', help='Skip confirmation prompt')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List available backups')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show configuration status')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export configuration as JSON')
    export_parser.add_argument('-o', '--output', help='Output path for JSON file')
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return 1
    
    # Execute command
    if args.command == 'backup':
        success = create_backup(args.output, args.include_logs)
        return 0 if success else 1
    
    elif args.command == 'restore':
        success = restore_backup(args.backup_file, args.force)
        return 0 if success else 1
    
    elif args.command == 'list':
        list_backups()
        return 0
    
    elif args.command == 'status':
        show_config_status()
        return 0
    
    elif args.command == 'export':
        success = export_config_json(args.output)
        return 0 if success else 1
    
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)