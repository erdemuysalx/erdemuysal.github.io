#!/usr/bin/env python3
"""
Static Website Generator

A simple static website generator that converts Markdown files to HTML
with configurable templates and directory structure.
"""

import os
import sys
import yaml
import markdown
import logging
import PyRSS2Gen
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Post:
    """Represents a post with metadata."""
    title: str
    date: datetime
    path: str
    content: str
    
    def __post_init__(self):
        """Ensure date is a datetime object."""
        if isinstance(self.date, str):
            try:
                self.date = datetime.strptime(self.date, '%Y-%m-%d')
            except ValueError:
                logger.warning(f"Invalid date format for post '{self.title}': {self.date}")
                self.date = datetime.now()


class WebsiteGenerator:
    """Main site generator class."""
    
    def __init__(self, config_path: str = 'config.yml'):
        """Initialize the website generator with configuration."""
        self.config = self._load_config(config_path)
        self._validate_config()
        self._setup_directories()
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
                logger.info(f"Configuration loaded from {config_path}")
                return config
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {config_path}")
            sys.exit(1)
        except yaml.YAMLError as e:
            logger.error(f"Error parsing configuration: {e}")
            sys.exit(1)
    
    def _validate_config(self) -> None:
        """Validate required configuration keys."""
        required_keys = [
            'website_url', 'website_name', 'author',
            'directories', 'files', 'misc'
        ]
        
        for key in required_keys:
            if key not in self.config:
                logger.error(f"Missing required configuration key: {key}")
                sys.exit(1)
                
        # Validate file paths exist
        file_paths = [
            self.config['files']['root_index'],
            self.config['files']['blog_index'],
            self.config['files']['contact_index'],
            self.config['templates']['header'],
            self.config['templates']['footer']
        ]
        
        for file_path in file_paths:
            if not os.path.exists(file_path):
                logger.error(f"Required file not found: {file_path}")
                sys.exit(1)
    
    def _setup_directories(self) -> None:
        """Create necessary output directories."""
        directories = [
            self.config['directories']['output'],
            self.config['directories']['blog_output']
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created directory: {directory}")
    
    def _read_file_safely(self, file_path: str, encoding: str = 'utf-8') -> str:
        """Safely read file content with error handling."""
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        except (FileNotFoundError, IOError) as e:
            logger.error(f"Error reading file {file_path}: {e}")
            raise
        except UnicodeDecodeError as e:
            logger.error(f"Encoding error reading file {file_path}: {e}")
            raise
    
    def _write_file_safely(self, file_path: str, content: str, encoding: str = 'utf-8') -> None:
        """Safely write file content with error handling."""
        try:
            # Ensure directory exists
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', encoding=encoding) as f:
                f.write(content)
            logger.debug(f"Written file: {file_path}")
        except (IOError, OSError) as e:
            logger.error(f"Error writing file {file_path}: {e}")
            raise
    
    def replace_template_variables(self, content: str, variables: Dict[str, str]) -> str:
        """Replace template variables in content."""
        for key, value in variables.items():
            placeholder = f"{{{{{key}}}}}"
            content = content.replace(placeholder, value)
        return content
    
    def extract_title_from_markdown(self, lines: List[str]) -> str:
        """Extract title from markdown content."""
        if not lines:
            return 'Untitled'
            
        first_line = lines[0].strip()
        if first_line.startswith('# '):
            return first_line[2:].strip()
        
        # Alternative: look for title in first few lines
        for line in lines[:5]:
            line = line.strip()
            if line.startswith('# '):
                return line[2:].strip()
                
        return 'Untitled'
    
    def extract_date_from_markdown(self, lines: List[str]) -> datetime:
        """Extract date from markdown content."""
        # Look for date in various formats and positions
        date_patterns = [
            '%d %b %Y', '%d %B %Y',
            '%b %d %Y','%B %d %Y',
            '%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d',
            '%d-%m-%Y', '%d/%m/%Y', '%d.%m.%Y',
            '%m-%d-%Y', '%m/%d/%Y', '%m.%d.%Y'
        ]
        
        # Check first few lines for date
        for line in lines[1:3]:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            for pattern in date_patterns:
                try:
                    return datetime.strptime(line, pattern)
                except ValueError:
                    continue
        
        # Default to current date
        logger.warning("No valid date found, using current date")
        return datetime.now()
    
    def convert_markdown_to_html(self, input_directory: str, output_directory: str) -> List[Post]:
        """Convert markdown files to HTML with improved error handling."""
        if not os.path.exists(input_directory):
            logger.warning(f"Input directory does not exist: {input_directory}")
            return []
        
        posts = []
        markdown_processor = markdown.Markdown(extensions=['extra', 'codehilite'])
        
        # Read template files once
        header_content = self._read_file_safely(self.config['templates']['header'])
        footer_content = self._read_file_safely(self.config['templates']['footer'])
        
        for root, _, files in os.walk(input_directory):
            for file in files:
                if not file.endswith('.md'):
                    continue
                    
                file_path = os.path.join(root, file)
                try:
                    md_content = self._read_file_safely(file_path)
                    lines = md_content.splitlines()
                    
                    # Extract metadata
                    title = self.extract_title_from_markdown(lines)
                    date = self.extract_date_from_markdown(lines)
                    
                    # Convert markdown to HTML
                    html_content = markdown_processor.convert(md_content)
                    
                    # Determine output path
                    relative_path = os.path.relpath(file_path, input_directory)
                    relative_path = os.path.splitext(relative_path)[0]  # Remove .md extension
                    
                    output_dir = os.path.join(output_directory, relative_path)
                    output_file = os.path.join(output_dir, 'index.html')
                    
                    # Prepare template variables
                    template_vars = {
                        'WEBSITE_NAME': self.config['website_name'],
                        'WEBSITE_URL': self.config['website_url'],
                        'AUTHOR': self.config['author'],
                        'TITLE': title
                    }
                    
                    # Process templates
                    processed_header = self.replace_template_variables(header_content, template_vars)
                    processed_footer = self.replace_template_variables(footer_content, template_vars)
                    
                    # Write final HTML
                    final_html = processed_header + html_content + processed_footer
                    self._write_file_safely(output_file, final_html)
                    
                    # Create post object
                    post = Post(
                        title=title,
                        date=date,
                        path=relative_path + '/',
                        content=html_content
                    )
                    posts.append(post)
                    
                    logger.info(f"Processed: {file_path} -> {output_file}")
                    
                except Exception as e:
                    logger.error(f"Error processing file {file_path}: {e}")
                    continue
        
        return posts
    
    def generate_index_page(self, posts: List[Post], contact_content: str = '') -> None:
        """Generate the main index page."""
        try:
            # Read and process root index
            root_content = self._read_file_safely(self.config['files']['root_index'])
            root_lines = root_content.splitlines()
            root_title = self.extract_title_from_markdown(root_lines)
            root_html = markdown.markdown(root_content)
            
            # Read templates
            header_content = self._read_file_safely(self.config['templates']['header'])
            footer_content = self._read_file_safely(self.config['templates']['footer'])
            
            # Prepare template variables
            template_vars = {
                'WEBSITE_NAME': self.config['website_name'],
                'WEBSITE_URL': self.config['website_url'],
                'AUTHOR': self.config['author'],
                'TITLE': root_title
            }
            
            # Process header
            processed_header = self.replace_template_variables(header_content, template_vars)
            
            # Build content
            posts_count = self.config['misc'].get('recent_posts_count', 5)
            recent_posts = sorted(posts, key=lambda p: p.date, reverse=True)[:posts_count]
            
            index_content = processed_header + root_html
            
            if recent_posts:
                index_content += '<ul class="blog">\n'
                for post in recent_posts:
                    date_str = post.date.strftime("%d %b %Y")
                    blog_dir = self.config['directories']['blog']
                    index_content += f'<li><span>{date_str}</span><a href="/{blog_dir}/{post.path}">{post.title}</a></li>\n'
                
                index_content += '</ul>\n'
                index_content += f'<p><a href="/{self.config["directories"]["blog"]}">View all blog posts &rarr;</a></p>\n'
            
            if contact_content:
                index_content += contact_content
            
            index_content += footer_content
            
            # Write index file
            output_path = os.path.join(self.config['directories']['output'], 'index.html')
            self._write_file_safely(output_path, index_content)
            
            logger.info(f"Generated index page: {output_path}")
            
        except Exception as e:
            logger.error(f"Error generating index page: {e}")
            raise
    

    def generate_posts_page(self, posts: List[Post], content_type: str, 
                        index_file_key: str, output_subdir: str, 
                        url_prefix: str = None) -> None:
        """Generate a generic list page for any content type (blog, projects, publications, etc.)"""
        try:
            # Read and process index content
            index_content = self._read_file_safely(self.config['files'][index_file_key])
            index_lines = index_content.splitlines()
            index_title = self.extract_title_from_markdown(index_lines)
            index_html = markdown.markdown(index_content)
            
            # Read templates
            header_content = self._read_file_safely(self.config['templates']['header'])
            footer_content = self._read_file_safely(self.config['templates']['footer'])
            
            # Prepare template variables
            template_vars = {
                'WEBSITE_NAME': self.config['website_name'],
                'WEBSITE_URL': self.config['website_url'],
                'AUTHOR': self.config['author'],
                'TITLE': index_title
            }
            
            # Process header
            processed_header = self.replace_template_variables(header_content, template_vars)
            
            # Build content
            sorted_posts = sorted(posts, key=lambda p: p.date, reverse=True)
            
            list_content = processed_header + index_html
            
            if sorted_posts:
                list_content += f'<ul class="{content_type}">\n'
                url_path = url_prefix or output_subdir
                for post in sorted_posts:
                    date_str = post.date.strftime("%d %b %Y")
                    list_content += f'<li><span>{date_str}</span><a href="/{url_path}/{post.path}">{post.title}</a></li>\n'
                list_content += '</ul>\n'
            
            list_content += footer_content
            
            # Write list file
            list_output_dir = os.path.join(self.config['directories']['output'], output_subdir)
            Path(list_output_dir).mkdir(parents=True, exist_ok=True)
            output_path = os.path.join(list_output_dir, 'index.html')
            self._write_file_safely(output_path, list_content)
            
            logger.info(f"Generated {content_type} list page: {output_path}")
            
        except Exception as e:
            logger.error(f"Error generating {content_type} list page: {e}")
            raise
    
    def generate_rss(self, posts: List[Post]) -> None:
        """Generate RSS feed from posts."""
        try:
            if not posts:
                logger.warning("No posts found, skipping RSS generation")
                return
            
            items = []
            posts_dir = self.config['directories']['blog']
            
            for post in posts:
                # Parse date and force time to midday
                date = post.date.replace(hour=12, minute=0, second=0, microsecond=0)
                item_link = f"{self.config['website_url']}/{posts_dir}/{post.path}"
                
                item = PyRSS2Gen.RSSItem(
                    title=post.title,
                    link=item_link,
                    description=post.content,
                    pubDate=date
                )
                
                items.append(item)
            
            # Sort items by date, most recent first
            items.sort(key=lambda x: x.pubDate, reverse=True)
            
            # Limit to recent posts if configured
            rss_limit = self.config['misc'].get('rss_post_limit', 20)
            items = items[:rss_limit]
            
            rss = PyRSS2Gen.RSS2(
                title=f"{self.config['website_name']} RSS Feed",
                link=self.config['website_url'],
                description=f"The official RSS Feed for {self.config['website_url']}",
                lastBuildDate=datetime.now(),
                items=items
            )
            
            # Generate RSS file path
            rss_filename = self.config['misc'].get('rss_filename', 'rss.xml')
            rss_file = os.path.join(self.config['directories']['output'], rss_filename)
            
            with open(rss_file, 'w', encoding='utf-8') as f:
                rss.write_xml(f)
            
            logger.info(f"Generated RSS feed: {rss_file} ({len(items)} items)")
            
        except Exception as e:
            logger.error(f"Error generating RSS feed: {e}")
            raise

    def build(self) -> None:
        """Build the entire website."""
        try:
            logger.info("Starting website build...")
            
            # Convert pages and blog posts
            pages = self.convert_markdown_to_html(
                self.config['directories']['pages'],
                self.config['directories']['output']
            )

            blog_posts = self.convert_markdown_to_html(
                self.config['directories']['blog'],
                os.path.join(self.config['directories']['output'], self.config['directories']['blog'])
            )
            
            # Get contact content
            contact_content = next(page for page in pages if page.title == "Contact").content

            # Generate index and blog list pages
            self.generate_index_page(blog_posts, contact_content)
            self.generate_posts_page(blog_posts, 'blog', 'blog_index', self.config['directories']['blog'])
            
            # Generate RSS feed
            if self.config['misc'].get('generate_rss', True):
                self.generate_rss(blog_posts)

            logger.info(f"Website build completed successfully! Output: {self.config['directories']['output']}")
            
        except Exception as e:
            logger.error(f"Website build failed: {e}")
            sys.exit(1)


def main():
    """Main entry point."""
    try:
        generator = WebsiteGenerator()
        generator.build()
    except KeyboardInterrupt:
        logger.info("Build interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()