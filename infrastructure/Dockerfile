# Lambda Docker image for Gym App
FROM public.ecr.aws/lambda/python:3.11

# Copy requirements
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
COPY infrastructure/requirements-lambda.txt ${LAMBDA_TASK_ROOT}/

# Install dependencies
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements-lambda.txt

# Copy application code
COPY backend/ ${LAMBDA_TASK_ROOT}/backend/
COPY frontend/ ${LAMBDA_TASK_ROOT}/frontend/
COPY data/ ${LAMBDA_TASK_ROOT}/data/

# Copy lambda handler
COPY infrastructure/lambda_handler.py ${LAMBDA_TASK_ROOT}/

# Set the handler
CMD ["lambda_handler.handler"]



