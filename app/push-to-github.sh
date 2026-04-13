#!/bin/bash

# Script to push Parts Extractor to GitHub
# Make sure you have created a repository on GitHub first.

echo "Parts Extractor - GitHub Push Helper"
echo "===================================="
echo ""

if [ -z "$1" ]; then
    echo "Error: No repository URL provided"
    echo ""
    echo "Usage:"
    echo "  bash push-to-github.sh <your-github-repo-url>"
    echo ""
    echo "Example:"
    echo "  bash push-to-github.sh https://github.com/yourusername/parts-extractor.git"
    echo ""
    echo "Steps to create a GitHub repository:"
    echo "  1. Go to https://github.com/new"
    echo "  2. Create a new repository named parts-extractor"
    echo "  3. Do not initialize it with a README"
    echo "  4. Copy the repository URL"
    echo "  5. Run this script with that URL"
    echo ""
    exit 1
fi

REPO_URL=$1

echo "Repository URL: $REPO_URL"
echo ""

echo "Adding GitHub remote..."
git remote add origin "$REPO_URL" 2>/dev/null || git remote set-url origin "$REPO_URL"

if [ $? -eq 0 ]; then
    echo "Remote configured successfully"
else
    echo "Remote may already exist, updating..."
fi

echo ""
echo "Current Git status:"
git status --short
echo ""

echo "Pushing to GitHub..."
git push -u origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "Successfully pushed to GitHub."
    echo "Repository:"
    echo "  $REPO_URL"
else
    echo ""
    echo "Failed to push to GitHub."
    echo "Common issues:"
    echo "  1. Authentication is required"
    echo "  2. The repository does not exist yet"
    echo "  3. The main branch is protected"
fi
