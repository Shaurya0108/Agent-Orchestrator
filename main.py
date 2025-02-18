import fastapi
import uvicorn
from dotenv import load_dotenv
import os
from fastapi import UploadFile, File, HTTPException
import shutil
import zipfile
from pathlib import Path
from agents.agent import AgentController
from agents.tools.code_change import CodeChangeHandler
from typing import List

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

@app.delete("/delete_repository")
async def delete_repository(repository_name: str):
    controller = AgentController()
    controller.delete_repository(repository_name)
    return {"status": "success", "message": f"Repository {repository_name} deleted"}

@app.get("/run_agent")
async def run_agent(repository_name: str = None, prompt: str = None):
    """
    Run the agent on a specified repository.

    Args:
        repository_name (str, optional): Name of the repository to analyze.
            If not provided, returns list of available repositories.
        prompt (str, optional): Question or instruction for the AI about the repository.

    Returns:
        dict: Analysis results, repository list, or AI response
    """
    controller = AgentController()

    # If no repository specified, return list of available repositories
    if not repository_name:
        repositories = controller.list_repositories()
        return {
            "status": "success",
            "available_repositories": repositories,
            "message": "Specify a repository_name query parameter to analyze a specific repository"
        }

    # Process repository with optional prompt
    result = await controller.process_repository_prompt(repository_name, prompt)
    if result["status"] == "error":
        raise HTTPException(status_code=404, detail=result["message"])

    return result

@app.post("/apply_changes")
async def apply_changes(repository_name: str, prompt: str):
    """
    Apply code changes to a repository based on the prompt.

    Args:
        repository_name (str): Name of the repository to modify
        prompt (str): Description of changes to make

    Returns:
        dict: Results of the modification attempt
    """
    controller = AgentController()

    # Verify repository exists
    repo_path = controller.get_repository_path(repository_name)
    if not repo_path:
        raise HTTPException(
            status_code=404,
            detail=f"Repository '{repository_name}' not found"
        )

    # Process repository with prompt
    result = await controller.process_repository_prompt(repository_name, prompt)

    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])

    # If changes were made, return the change results
    if "gpt_response" in result and isinstance(result["gpt_response"], dict):
        response = result["gpt_response"]
        if "change_results" in response:
            return {
                "status": "success",
                "changes": response["change_results"],
                "explanation": response.get("explanation", ""),
                "diff_summary": response.get("diff_summary", "")
            }

    return {
        "status": "error",
        "message": "No code changes were generated from the prompt"
    }

@app.post("/revert_changes")
async def revert_changes(repository_name: str, file_paths: List[str]):
    """
    Revert changes made to specified files in a repository.

    Args:
        repository_name (str): Name of the repository
        file_paths (List[str]): List of file paths to revert

    Returns:
        dict: Results of the reversion attempt
    """
    controller = AgentController()

    # Verify repository exists
    repo_path = controller.get_repository_path(repository_name)
    if not repo_path:
        raise HTTPException(
            status_code=404,
            detail=f"Repository '{repository_name}' not found"
        )

    # Create code handler
    code_handler = CodeChangeHandler(repo_path)

    # Attempt to revert changes
    result = code_handler.revert_changes(file_paths)

    if result["status"] == "error":
        raise HTTPException(
            status_code=400,
            detail={"message": "Error reverting changes", "errors": result["errors"]}
        )

    return result

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
