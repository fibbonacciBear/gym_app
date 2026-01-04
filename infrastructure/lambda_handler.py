"""Lambda handler for Gym App using Mangum."""
from mangum import Mangum
from backend.main import app

# Mangum adapter for AWS Lambda
handler = Mangum(app, lifespan="off")





