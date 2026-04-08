#!/bin/bash

# Script to push MobileSentrix Tool to GitHub
# Make sure you have created a repository on GitHub first!

echo "🚀 MobileSentrix Tool - GitHub Push Helper"
echo "==========================================="
echo ""

# Check if user has provided repository URL
if [ -z "$1" ]; then
    echo "❌ Error: No repository URL provided"
    echo ""
    echo "Usage:"
    echo "  bash push-to-github.sh <your-github-repo-url>"
    echo ""
    echo "Example:"
    echo "  bash push-to-github.sh https://github.com/yourusername/mobilesentrix-tool.git"
    echo ""
    echo "Steps to create a GitHub repository:"
    echo "  1. Go to https://github.com/new"
    echo "  2. Create a new repository (name: mobilesentrix-tool)"
    echo "  3. DO NOT initialize with README (we already have one)"
    echo "  4. Copy the repository URL"
    echo "  5. Run this script with that URL"
    echo ""
    exit 1
fi

REPO_URL=$1

echo "📍 Repository URL: $REPO_URL"
echo ""

# Add remote
echo "➕ Adding GitHub remote..."
git remote add origin "$REPO_URL" 2>/dev/null || git remote set-url origin "$REPO_URL"

if [ $? -eq 0 ]; then
    echo "✅ Remote added successfully"
else
    echo "⚠️  Remote may already exist, updating..."
fi

echo ""

# Show current status
echo "📊 Current Git Status:"
git status --short
echo ""

# Push to GitHub
echo "🚀 Pushing to GitHub..."
git push -u origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Successfully pushed to GitHub!"
    echo ""
    echo "🎉 Your repository is now live at:"
    echo "   $REPO_URL"
    echo ""
    echo "Next steps:"
    echo "  - Visit your repository on GitHub"
    echo "  - Add a description and topics"
    echo "  - Enable GitHub Pages (if desired)"
    echo "  - Share with others!"
else
    echo ""
    echo "❌ Failed to push to GitHub"
    echo ""
    echo "Common issues:"
    echo "  1. Authentication required - you may need to:"
    echo "     - Set up SSH keys: https://docs.github.com/en/authentication/connecting-to-github-with-ssh"
    echo "     - Use Personal Access Token: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token"
    echo ""
    echo "  2. Repository doesn't exist - make sure you created it on GitHub first"
    echo ""
    echo "  3. Branch protection - check if 'main' branch has protection rules"
fi
