# api/backup_routes.py
from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import jwt_required, get_jwt
import os
import subprocess
import json
from datetime import datetime
from pathlib import Path

backup_api = Blueprint('backup_api', __name__)

# Get paths dynamically
CURRENT_USER = os.environ.get('USER', 'radxa')
EFIO_DIR = Path.home() / "efio"
BACKUP_DIR = Path.home() / "efio_backups"
BACKUP_SCRIPT = EFIO_DIR / "backup_restore.py"

def admin_required():
    """Check if current user is admin"""
    claims = get_jwt()
    return claims.get('role') == 'admin'

@backup_api.route('/api/backup/list', methods=['GET'])
@jwt_required()
def list_backups():
    """List all available backup files"""
    try:
        # Create backup dir if doesn't exist
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        
        backups = []
        for backup_file in sorted(BACKUP_DIR.glob("*.tar.gz"), 
                                  key=lambda p: p.stat().st_mtime, 
                                  reverse=True):
            stat = backup_file.stat()
            backups.append({
                "filename": backup_file.name,
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "includes_logs": "logs" not in backup_file.name.lower()
            })
        
        return jsonify({"backups": backups, "count": len(backups)}), 200
        
    except Exception as e:
        print(f"❌ Error listing backups: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@backup_api.route('/api/backup/create', methods=['POST'])
@jwt_required()
def create_backup():
    """Create new backup"""
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    try:
        data = request.get_json() or {}
        include_logs = data.get('include_logs', False)
        
        print(f"📦 Creating backup (logs={include_logs})...")
        
        # Check if backup script exists
        if not BACKUP_SCRIPT.exists():
            return jsonify({
                "error": f"Backup script not found: {BACKUP_SCRIPT}"
            }), 500
        
        # Ensure backup directory exists
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"efio_backup_{timestamp}.tar.gz"
        output_path = BACKUP_DIR / filename
        
        # Build command
        cmd = [
            "python3",
            str(BACKUP_SCRIPT),
            "backup",
            "-o", str(output_path)
        ]
        
        if include_logs:
            cmd.append("--include-logs")
        
        print(f"🔧 Running: {' '.join(cmd)}")
        
        # Execute backup command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(EFIO_DIR)
        )
        
        print(f"📤 Stdout: {result.stdout}")
        print(f"📤 Stderr: {result.stderr}")
        print(f"📤 Return code: {result.returncode}")
        
        if result.returncode != 0:
            return jsonify({
                "error": "Backup failed",
                "details": result.stderr,
                "stdout": result.stdout
            }), 500
        
        # Verify file was created
        if not output_path.exists():
            return jsonify({
                "error": "Backup file not created",
                "expected_path": str(output_path)
            }), 500
        
        # Get file size
        size = output_path.stat().st_size
        
        print(f"✅ Backup created: {filename} ({size} bytes)")
        
        return jsonify({
            "message": "Backup created successfully",
            "filename": filename,
            "size": size,
            "created": datetime.now().isoformat()
        }), 200
        
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Backup timeout (>60s)"}), 500
    except Exception as e:
        print(f"❌ Backup error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@backup_api.route('/api/backup/download', methods=['GET'])
@jwt_required()
def download_backup():
    """Download backup file"""
    try:
        filename = request.args.get('filename')
        
        if not filename:
            return jsonify({"error": "filename required"}), 400
        
        backup_path = BACKUP_DIR / filename
        
        if not backup_path.exists():
            return jsonify({"error": "Backup file not found"}), 404
        
        return send_file(
            backup_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/gzip'
        )
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@backup_api.route('/api/backup/restore', methods=['POST'])
@jwt_required()
def restore_backup():
    """Restore from backup"""
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    try:
        data = request.get_json()
        filename = data.get('filename')
        
        if not filename:
            return jsonify({"error": "filename required"}), 400
        
        backup_path = BACKUP_DIR / filename
        
        if not backup_path.exists():
            return jsonify({"error": "Backup file not found"}), 404
        
        print(f"📦 Restoring from: {filename}")
        
        # Execute restore command
        cmd = [
            "python3",
            str(BACKUP_SCRIPT),
            "restore",
            str(backup_path),
            "-f"  # Force without confirmation
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(EFIO_DIR)
        )
        
        if result.returncode != 0:
            return jsonify({
                "error": "Restore failed",
                "details": result.stderr
            }), 500
        
        print(f"✅ Restored from: {filename}")
        
        return jsonify({
            "message": "Backup restored successfully",
            "note": "System restart recommended"
        }), 200
        
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Restore timeout"}), 500
    except Exception as e:
        print(f"❌ Restore error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@backup_api.route('/api/backup/delete', methods=['POST'])
@jwt_required()
def delete_backup():
    """Delete backup file"""
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    try:
        data = request.get_json()
        filename = data.get('filename')
        
        if not filename:
            return jsonify({"error": "filename required"}), 400
        
        backup_path = BACKUP_DIR / filename
        
        if not backup_path.exists():
            return jsonify({"error": "Backup file not found"}), 404
        
        # Delete file
        backup_path.unlink()
        
        print(f"🗑️ Deleted backup: {filename}")
        
        return jsonify({"message": "Backup deleted"}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500