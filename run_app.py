# run_app.py
import uvicorn
from main import app
from DB.init import initialize_database

if __name__ == "__main__":
    initialize_database()  
    uvicorn.run(app, host="0.0.0.0", port=9000, reload=False)
