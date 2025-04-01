#!/bin/bash

# GitHub repository setup script
# Run this script after creating a GitHub repository

# Check if GitHub URL is provided
if [ -z "$1" ]; then
  echo "Usage: $0 <github-repo-url>"
  echo "Example: $0 https://github.com/yourusername/whatsapp-monitoring.git"
  exit 1
fi

GITHUB_URL=$1

# Add all files
git add .

# Make the initial commit
git commit -m "Initial commit: WhatsApp Monitoring System

This includes:
- Claude AI integration for answering questions
- ERPNext integration for task management
- Environment-based configuration
- Proper package structure"

# Set up the remote repository
git remote add origin $GITHUB_URL

# Push to GitHub
git push -u origin master

echo "Repository pushed to GitHub: $GITHUB_URL"
echo "You can now clone it from there onto other systems."