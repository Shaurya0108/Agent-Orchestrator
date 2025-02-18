import datetime
from pathlib import Path
import logging
import difflib
import os
from typing import Dict, Optional, List
import json

logger = logging.getLogger(__name__)

class CodeChangeHandler:
    """Handles implementation of code changes from GPT responses"""
    
    def __init__(self, repository_path: Path):
        self.repository_path = repository_path
        self.backup_dir = repository_path / ".code_backup"
        self._ensure_backup_dir()
        
    def _ensure_backup_dir(self):
        """Ensures backup directory exists"""
        self.backup_dir.mkdir(exist_ok=True)
        
    def backup_file(self, file_path: Path) -> Path:
        """Creates a backup of a file before modification"""
        if not file_path.exists():
            return None
            
        relative_path = file_path.relative_to(self.repository_path)
        backup_path = self.backup_dir / relative_path
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        
        if backup_path.exists():
            # Add timestamp if backup already exists
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.backup_dir / f"{relative_path}.{timestamp}"
            
        with open(file_path, 'r') as src, open(backup_path, 'w') as dst:
            dst.write(src.read())
            
        return backup_path

    def generate_patch(self, original_content: str, modified_content: str, file_path: str) -> str:
        """Generates a unified diff patch between original and modified content"""
        original_lines = original_content.splitlines(keepends=True)
        modified_lines = modified_content.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=file_path,
            tofile=file_path,
            lineterm=''
        )
        
        return ''.join(diff)

    def apply_changes(self, changes: Dict[str, str]) -> Dict[str, str]:
        """
        Applies the specified changes to files in the repository.
        
        Args:
            changes: Dict mapping file paths to their new content
            
        Returns:
            Dict containing status of each file modification and generated patches
        """
        results = {
            "status": "success",
            "modified_files": [],
            "errors": [],
            "patches": {}
        }
        
        for file_path_str, new_content in changes.items():
            try:
                file_path = self.repository_path / file_path_str
                logger.debug(f"Applying changes to {file_path}")
                
                # Create parent directories if needed
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Backup existing file
                if file_path.exists():
                    original_content = file_path.read_text()
                    backup_path = self.backup_file(file_path)
                    patch = self.generate_patch(original_content, new_content, file_path_str)
                    results["patches"][file_path_str] = patch
                else:
                    original_content = ""
                    patch = self.generate_patch("", new_content, file_path_str)
                    results["patches"][file_path_str] = patch
                
                # Write new content
                file_path.write_text(new_content)
                results["modified_files"].append(file_path_str)
                
            except Exception as e:
                error_msg = f"Error modifying {file_path_str}: {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
                
        if results["errors"]:
            results["status"] = "partial_success" if results["modified_files"] else "error"
            
        return results

    def revert_changes(self, file_paths: List[str]) -> Dict[str, str]:
        """
        Reverts changes for specified files using their backups
        
        Args:
            file_paths: List of file paths to revert
            
        Returns:
            Dict containing status of reversion operation
        """
        results = {
            "status": "success",
            "reverted_files": [],
            "errors": []
        }
        
        for file_path_str in file_paths:
            try:
                file_path = self.repository_path / file_path_str
                backup_path = self.backup_dir / file_path_str
                
                if not backup_path.exists():
                    raise FileNotFoundError(f"No backup found for {file_path_str}")
                    
                # Copy backup back to original location
                with open(backup_path, 'r') as src, open(file_path, 'w') as dst:
                    dst.write(src.read())
                    
                results["reverted_files"].append(file_path_str)
                
            except Exception as e:
                error_msg = f"Error reverting {file_path_str}: {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
                
        if results["errors"]:
            results["status"] = "partial_success" if results["reverted_files"] else "error"
            
        return results

    def get_diff_summary(self, patches: Dict[str, str]) -> str:
        """Generates a human-readable summary of changes from patches"""
        summary = []
        for file_path, patch in patches.items():
            summary.append(f"\nFile: {file_path}")
            summary.append("-" * 40)
            summary.append(patch)
            
        return "\n".join(summary)
