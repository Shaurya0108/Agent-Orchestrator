import fastapi
import uvicorn
from dotenv import load_dotenv
import os
from utils import ThreadWithExc
from fastapi import UploadFile, File
import shutil
import zipfile
from pathlib import Path
from fastapi import HTTPException
from agents.agent import AgentOrchestrator

load_dotenv()

app = fastapi.FastAPI()

@app.get("/")
def read_root():
    return {"message": "Welcome to LangHub! Go to /docs to get started."}

@app.post("/upload_repository")
async def upload_repository(file: UploadFile = File(...)):
    """User uploads a local zip repository, which is then uploaded to the server where the API is running.

    Args:
        file (UploadFile): The zip file to be uploaded

    Returns:
        dict: Status of the upload and extraction
    """
    try:
        # Create a temporary file to store the upload
        with open(f"temp_{file.filename}", "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)

        # Extract the zip file
        with zipfile.ZipFile(f"temp_{file.filename}", "r") as zip_ref:
            extract_dir = upload_dir / Path(file.filename).stem
            zip_ref.extractall(extract_dir)

        # Clean up the temporary file
        os.remove(f"temp_{file.filename}")
        return {
            "status": "success",
            "message": f"Repository uploaded and extracted to {extract_dir}",
            "filename": file.filename
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error processing upload: {str(e)}"
        }

@app.get("/run_agent")
def run_agent(repository_name: str = None):
    """
    Run the agent on a specified repository.

    Args:
        repository_name (str, optional): Name of the repository to analyze.
            If not provided, returns list of available repositories.

    Returns:
        dict: Analysis results or repository list
    """
    orchestrator = AgentOrchestrator()

    # If no repository specified, return list of available repositories
    if not repository_name:
        repositories = orchestrator.list_repositories()
        return {
            "status": "success",
            "available_repositories": repositories,
            "message": "Specify a repository_name query parameter to analyze a specific repository"
        }

    # Run analysis on specified repository
    result = orchestrator.analyze_repository(repository_name)
    if result["status"] == "error":
        raise HTTPException(status_code=404, detail=result["message"])

    return result

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
