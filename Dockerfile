FROM node:22-alpine AS frontend-build

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm install

ARG VITE_API_BASE_URL=
ARG VITE_DEFAULT_FISCAL_YEAR=2027
ARG VITE_BUILD_VERSION=local
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_DEFAULT_FISCAL_YEAR=${VITE_DEFAULT_FISCAL_YEAR}
ENV VITE_BUILD_VERSION=${VITE_BUILD_VERSION}

COPY frontend/ ./
RUN npm run build


FROM python:3.12-slim AS app

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/alembic.ini ./alembic.ini
COPY backend/alembic ./alembic
COPY --from=frontend-build /frontend/dist ./app/static

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
