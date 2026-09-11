from fastapi import FastAPI

# Create FastAPI app instance
app = FastAPI()

# Define a simple GET endpoint
@app.get("/")
def read_root():
    return {"message": "Hello World"}
# Explanation:

# from fastapi import FastAPI: Imports the FastAPI class.
# app = FastAPI(): Creates an application instance (used by Uvicorn to run the server).
# @app.get("/"): Defines the root (/) route for GET requests.
# def read_root(): A function that runs when the route is accessed.
# return {"message": "Hello World"}: Returns a JSON response.