from setuptools import setup, find_packages

setup(
    name="spotify_recommendation_challenge",
    version="0.1.0",
    packages=find_packages(),  
    install_requires=[
        "pandas",
        "numpy",
        "scikit-learn",
    ],
    python_requires=">=3.12",
)
