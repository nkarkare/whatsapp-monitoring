from setuptools import setup, find_packages

setup(
    name="whatsapp-monitoring",
    version="0.1.0",
    description="WhatsApp monitoring with Claude AI and ERPNext integration",
    author="Your Name",
    author_email="your.email@example.com",
    packages=find_packages(),
    install_requires=[
        "requests>=2.28.1",
        "python-dateutil>=2.8.2",
    ],
    scripts=[
        "run_monitor.sh",
    ],
    python_requires=">=3.8",
)