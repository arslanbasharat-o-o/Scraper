# 🛍️ MobileSentrix Scraping Tool

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Fly.io-blueviolet?style=for-the-badge&logo=fly.io)](https://mobilesentrix-tool-v8.fly.dev/)
[![Python](https://img.shields.io/badge/Python-3.8+-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0+-green?style=for-the-badge&logo=flask)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

A powerful web scraping tool designed for extracting product data from mobile phone parts and accessories websites. Features a modern web interface, real-time statistics, advanced filtering, and comprehensive data management.

## 🚀 Live Demo

**Try it now:** [https://mobilesentrix-tool-v8.fly.dev/](https://mobilesentrix-tool-v8.fly.dev/)

Deployed on Fly.io with automatic scaling and global edge network.

## ✨ Features

### 🎯 Core Functionality
- **Multi-Site Scraping**: Support for multiple mobile parts suppliers including MobileSentrix, XCellParts, TXParts, and more
- **Intelligent Extraction**: Automatically extracts product titles, prices, images, and SKUs
- **Parallel Processing**: Fast concurrent scraping with configurable thread pools
- **Price Adjustment Rules**: Apply percentage-based or absolute price modifications
- **Comparison Engine**: Compare and analyze price differences across scraping sessions

### 📊 Statistics & Analytics
- **Real-Time Dashboard**: 12 live statistics cards tracking your scraping activity
- **Database Overview**: Total sessions, items scraped, unique models, recent activity
- **Performance Metrics**: Success rate, average price, highest/lowest prices
- **Site Analytics**: Track which sites you've scraped most frequently

### 🗂️ History Management
- **Session History**: Browse all previous scraping sessions with detailed metadata
- **Advanced Filtering**: Filter by date range, item count, site, or search terms
- **Data Export**: Export individual sessions or entire history to XLSX format
- **Cleanup Tools**: Remove old sessions with flexible date/time options or delete all history

### 🎨 User Interface
- **Modern Design**: Dark/Light theme with glassmorphism effects
- **Responsive Layout**: Works perfectly on desktop, tablet, and mobile devices
- **Live Clock**: Real-time Pakistan Standard Time (PKT) display
- **Status Indicators**: Visual feedback for all operations
- **Interactive Modals**: Rich detail views and cleanup dialogs

### 🖼️ Image Conversion
- **Format Conversion**: Convert images between JPEG, PNG, and WebP formats
- **Bulk Processing**: Convert multiple images at once
- **Quality Control**: Adjustable compression settings
- **Download Support**: Save converted images directly

### ⚙️ Advanced Features
- **Scheduler (Optional)**: Set up automated scraping jobs with APScheduler
- **Database Management**: SQLite database with optimized queries
- **Error Handling**: Comprehensive error tracking and user-friendly messages
- **Session Management**: Persistent theme preferences and filter states

## 🚀 Getting Started

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)
- Modern web browser (Chrome, Firefox, Safari, or Edge)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/mobilesentrix-tool.git
cd mobilesentrix-tool
```

2. **Create a virtual environment**
```bash
python -m venv .venv
```

3. **Activate the virtual environment**
- **macOS/Linux:**
  ```bash
  source .venv/bin/activate
  ```
- **Windows:**
  ```bash
  .venv\Scripts\activate
  ```

4. **Install dependencies**
```bash
pip install -r requirements.txt
```

5. **Run the application**
```bash
python app.py
```

6. **Open in browser**
Navigate to `http://127.0.0.1:5001`

## 📦 Dependencies

### Core Requirements
- **Flask**: Web framework
- **Requests**: HTTP library for web scraping
- **BeautifulSoup4**: HTML parsing
- **Pillow**: Image processing
- **openpyxl**: Excel file generation

### Optional
- **APScheduler**: Task scheduling (for automated scraping)

## 🏗️ Project Structure

```
mobilesentrix_tool/
├── app.py                      # Main Flask application
├── database.py                 # Database management
├── scraper_engine.py           # Core scraping logic
├── xcell_scraper_engine.py     # XCellParts specialized scraper
├── txparts_scraper_engine.py   # TXParts specialized scraper
├── requirements.txt            # Python dependencies
├── mise.toml                   # Development environment config
├── Dockerfile                  # Docker configuration
├── fly.toml                    # Fly.io deployment config
├── static/
│   ├── css/
│   │   ├── common.css         # Shared styles
│   │   ├── main.css           # Main page styles
│   │   ├── history.css        # History page styles
│   │   ├── image-converter.css
│   │   └── loading.css        # Loading animations
│   └── js/
│       ├── main.js            # Main page logic
│       └── history.js         # History page logic
└── templates/
    ├── index.html             # Main scraping interface
    ├── history.html           # History dashboard
    └── image-converter.html   # Image conversion tool
```

## 🎯 Usage Guide

### Basic Scraping

1. **Enter Product URLs**: Paste one or more product URLs (one per line)
2. **Set Price Rules** (optional):
   - Percentage off: Reduce all prices by X%
   - Absolute off: Reduce all prices by $X
3. **Click Extract**: Start the scraping process
4. **View Results**: See extracted products with prices and images
5. **Export**: Download results as XLSX

### Comparing Sessions

1. Navigate to the **History** page
2. Click any previous session card
3. Click **"Compare with Current"** button
4. View side-by-side price comparison
5. See price differences highlighted

### Managing History

- **Search**: Filter sessions by URL, site, or ID
- **Date Range**: Filter by start and end dates
- **Minimum Items**: Show only sessions with X+ items
- **Site Filter**: Filter by specific website
- **Export**: Download individual or all sessions
- **Cleanup**: Remove old sessions by age or delete all

### Image Conversion

1. Go to **Image Converter** page
2. Enter image URLs (one per line)
3. Select target format (JPEG/PNG/WebP)
4. Set quality (1-100)
5. Convert and download

## 🔧 Configuration

### Environment Variables
No environment variables required for basic operation. Optional scheduler configuration can be set via the web UI.

### Database
SQLite database (`mobile_items.db`) is created automatically on first run.

### Ports
Default port: `5001` (configurable in `app.py`)

## 🐳 Docker Deployment

```bash
# Build the image
docker build -t mobilesentrix-tool .

# Run the container
docker run -p 5001:5001 mobilesentrix-tool
```

## ☁️ Cloud Deployment

### Fly.io (Current Deployment)

**Live App:** [https://mobilesentrix-tool-v8.fly.dev/](https://mobilesentrix-tool-v8.fly.dev/)

The app is currently deployed and running on Fly.io with:
- ✅ Global edge network
- ✅ Automatic SSL/HTTPS
- ✅ Auto-scaling based on traffic
- ✅ Persistent storage for database

To deploy your own instance:
```bash
fly launch
fly deploy
```

Configuration is pre-set in `fly.toml`.

## 🎨 Themes

The application supports both **Dark** and **Light** themes:
- Toggle via the switch in the top-right corner
- Preference is saved per browser session
- Consistent styling across all pages

## 📊 Statistics Explained

- **Total Sessions**: Number of scraping sessions performed
- **Items Scraped**: Total products extracted
- **Unique Models**: Estimated unique product models
- **Recent (30d)**: Sessions in the last 30 days
- **Database Size**: Current SQLite database file size
- **Sites Scraped**: Number of different websites scraped
- **Avg Price**: Average product price across all items
- **Success Rate**: Percentage of items with valid prices
- **Top Site**: Most frequently scraped website
- **Latest Session**: Date of most recent scraping
- **Highest Price**: Most expensive item found
- **Lowest Price**: Cheapest item found

## 🛠️ Troubleshooting

### Scraping Issues
- **403 Forbidden**: Some sites block automated requests. Try different URLs.
- **Empty Results**: Site structure may have changed. Check console logs.
- **Slow Performance**: Reduce number of URLs or increase timeout values.

### Database Issues
- **Locked Database**: Close all other connections to the database file.
- **Corrupted Data**: Delete `mobile_items.db` to start fresh.

### UI Issues
- **Dark/Light Theme**: Clear browser cache and reload.
- **Statistics Not Updating**: Click the Refresh button in History page.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Built with Flask and modern web technologies
- Beautiful UI inspired by glassmorphism design trends
- Icon emojis for enhanced visual communication

## 📧 Support

For questions or issues, please open an issue on GitHub or contact the maintainer.

---

**Made with ❤️ for efficient mobile parts data extraction**
