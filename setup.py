from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="jerry-in-a-box",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A chord recognition and song identification system for Jerry Garcia songs",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/bluitz/jerry-in-a-box",
    packages=find_packages(),
    install_requires=[
        "numpy>=1.21.0",
        "librosa>=0.9.2",
        "sounddevice>=0.4.4",
        "scipy>=1.7.0",
        "pyaudio>=0.2.12",
        "python-levenshtein>=0.12.2",
        "pygame>=2.1.2",
        "SpeechRecognition>=3.8.1",
        "pydub>=0.25.1",
        "requests>=2.26.0",
        "python-dotenv>=0.19.0",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
    entry_points={
        'console_scripts': [
            'jerry-in-a-box=jerry_in_a_box.main:main',
        ],
    },
)
