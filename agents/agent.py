from pathlib import Path
from typing import Dict, Optional

class RepositoryAgent:
    def __init__(self, repository_path: Path):
        self.repository_path = repository_path
        self.analysis_results = {}

    def analyze_repository(self) -> Dict:
        """
        Analyze the repository structure and contents.

        Returns:
            Dict: Analysis results including file structure and basic stats
        """
        try:
            # Get repository structure
            files = list(self.repository_path.rglob("*"))

            # Basic statistics
            stats = {
                "total_files": len([f for f in files if f.is_file()]),
                "total_directories": len([f for f in files if f.is_dir()]),
                "file_types": {},
                "repository_name": self.repository_path.name
            }

            # Count file types
            for file in files:
                if file.is_file():
                    file_type = file.suffix
                    stats["file_types"][file_type] = stats["file_types"].get(file_type, 0) + 1

            self.analysis_results = stats
            return {
                "status": "success",
                "results": stats
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Error analyzing repository: {str(e)}"
            }

class AgentOrchestrator:
    def __init__(self):
        self.uploads_dir = Path("uploads")

    def list_repositories(self) -> list:
        """List all available repositories in the uploads directory."""
        if not self.uploads_dir.exists():
            return []
        return [d.name for d in self.uploads_dir.iterdir() if d.is_dir()]

    def get_repository_path(self, repository_name: str) -> Optional[Path]:
        """Get the path to a specific repository."""
        repo_path = self.uploads_dir / repository_name
        return repo_path if repo_path.exists() else None

    def analyze_repository(self, repository_name: str) -> Dict:
        """
        Analyze a specific repository using the RepositoryAgent.

        Args:
            repository_name (str): Name of the repository to analyze

        Returns:
            Dict: Analysis results or error message
        """
        repo_path = self.get_repository_path(repository_name)
        if not repo_path:
            return {
                "status": "error",
                "message": f"Repository '{repository_name}' not found"
            }

        agent = RepositoryAgent(repo_path)
        return agent.analyze_repository()
