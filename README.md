# Flim

Flim is a cinema information and scheduling application. This README provides detailed instructions on how to deploy and run Flim using Docker and Makefile commands.

## Prerequisites

- Docker and Docker Compose installed on your machine
- Make installed on your machine
- Node.js and npm installed for front-end development

## Development Setup

You can run both the front-end and back-end simultaneously using the provided Makefile commands.

### Starting Development Servers

To launch both the front-end and back-end in development mode with hot reload:

```bash
make dev
```

This command will:

- Start the backend server using `uvicorn` with auto-reload enabled
- Start the front-end development server using `npm run dev`

### Running Back-end Only

To run only the back-end server:

```bash
make backend
```

This runs the FastAPI backend with hot reload enabled:

```bash
uvicorn main:app --reload
```

### Running Front-end Only

To run only the front-end server:

```bash
make frontend
```

This runs the front-end development server:

```bash
npm run dev
```

## Docker Deployment

Flim can be deployed using Docker for easier environment management.

### Build Docker Images

To build the Docker images for both front-end and back-end:

```bash
make build
```

### Run Containers

To start the containers defined in `docker-compose.yml`:

```bash
make up
```

This will start the backend and frontend containers and allow you to access the app locally.

### Stop Containers

To stop and remove the running containers:

```bash
make down
```

## API Usage Examples

The `api` object provides methods to retrieve cinema data:

- Get top cities:

```python
ret = api.get_top_villes()
```

- Get movies for a cinema on a specific date:

```python
data = api.get_movies("P0571", "2025-09-10")
```

- Get list of departments:

```python
ret = api.get_departements()
```

- Get list of circuits:

```python
ret = api.get_circuit()
```

- Get cinemas in a department:

```python
cinemas = api.get_cinema("departement-83191")
```

- Get showtimes for a cinema on a date:

```python
data = api.get_showtime("W2920", "2024-01-01")
```

## Additional Notes

- Ensure environment variables are set correctly for API keys and configuration.
- For production deployment, consider configuring HTTPS and persistent storage.

---

This README should help you get started with development and deployment of Flim using Docker and Makefile workflows.
