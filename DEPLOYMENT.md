# Backend Deployment Guide

## Deploying to Cloud Platforms

### Railway
1. Create a new project on Railway
2. Connect your GitHub repository
3. Add the following environment variables:
   - `DATABASE_URL`: Your PostgreSQL connection string
   - `SECRET_KEY`: Your JWT secret key
4. Deploy the application

### Render
1. Create a new Web Service on Render
2. Connect your GitHub repository
3. Set the following environment variables:
   - `DATABASE_URL`: Your PostgreSQL connection string
   - `SECRET_KEY`: Your JWT secret key
4. Use the Dockerfile in the repository for deployment

### Heroku
1. Create a new app on Heroku
2. Deploy using the Heroku CLI or GitHub integration
3. Set the required environment variables
4. Use the `requirements.txt` for dependencies

## Environment Variables

The following environment variables are required for deployment:

```
DATABASE_URL=postgresql+asyncpg://username:password@host:port/database
SECRET_KEY=your-super-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

## Database Setup

The application uses PostgreSQL with asyncpg. Make sure your database URL is properly formatted:
`postgresql+asyncpg://username:password@host:port/database`

## API Endpoint

Once deployed, your API will be available at:
`https://your-app-name.onrender.com/api/v1/`

Update your frontend's `NEXT_PUBLIC_API_BASE_URL` to point to this endpoint.