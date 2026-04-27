#!/usr/bin/env python3
"""
Fast ZIP compression script using Python zipfile
Compresses directories with optimal compression
"""

import sys
import json
import os
import zipfile
from pathlib import Path

def create_zip(source_dir, output_path, compression_level=9):
    """
    Create a ZIP file from a directory with optimal compression
    Returns metadata about the ZIP file
    """
    try:
        source_path = Path(source_dir)
        if not source_path.exists() or not source_path.is_dir():
            return {'success': False, 'error': f'Directory not found: {source_dir}'}
        
        # Create parent directory for output if needed
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        # Create ZIP file with compression
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=compression_level) as zipf:
            # Add all files from source directory
            for root, dirs, files in os.walk(source_path):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(source_path.parent)
                    zipf.write(file_path, arcname)
        
        # Get file stats
        zip_size = output_path_obj.stat().st_size
        
        return {
            'success': True,
            'path': output_path,
            'size': zip_size,
            'size_mb': round(zip_size / (1024 * 1024), 2),
            'file_count': len(list(source_path.rglob('*'))),
            'compression': 'DEFLATE'
        }
    
    except Exception as e:
        return {'success': False, 'error': f'ZIP creation failed: {str(e)}'}

def main():
    """Main entry point"""
    if len(sys.argv) < 3:
        print(json.dumps({'success': False, 'error': 'Usage: create_zip.py <source_dir> <output_path> [compression_level]'}))
        sys.exit(1)
    
    source_dir = sys.argv[1]
    output_path = sys.argv[2]
    compression_level = int(sys.argv[3]) if len(sys.argv) > 3 else 9
    
    result = create_zip(source_dir, output_path, compression_level)
    print(json.dumps(result))

if __name__ == '__main__':
    main()
