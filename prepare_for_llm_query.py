import os
"""
This script collects and combines the contents of all .py and .md files starting from a specified directory,
excluding certain directories and files. The combined content is then saved to a new file.
Functions:
- collect_files(starting_dir): Collects all .py and .md files starting from the specified directory, excluding certain directories and files.
- combine_file_contents(file_paths): Combines the contents of the specified files into a single formatted string.
- main(): Main function to collect and combine files, and save the combined content to a new file.
Usage:
Run this script directly to collect and combine files from the 'LocalYoutubeAIHelper-Python' directory within the current working directory.
The combined content will be saved to 'combined_files_for_llm.txt'.
Note:
This script is designed to prepare file contents for input to an LLM (Large Language Model) which cannot handle input files directly but can process messages.
"""

def collect_files(starting_dir):
    """Collect all .py and .md files starting from the specified directory."""
    excluded_dirs = {'.venv', 'venv', '__pycache__','.git','videos','news','transcripts'}
    excluded_files = {__file__}
    collected_files = []
    for root, dirs, files in os.walk(starting_dir):
        # Exclude specified directories
        dirs[:] = [d for d in dirs if d not in excluded_dirs]
        for file in files:
            full_path = os.path.join(root, file)
            allowed_extensions = ['.py', '.md','.bat','.txt']
            if any(file.endswith(ext) for ext in allowed_extensions) and full_path != os.path.abspath(__file__):
                collected_files.append(full_path)
    return collected_files

def combine_file_contents(file_paths):
    """Combine the contents of the specified files into a single formatted string."""
    combined_content = []
    for file_path in file_paths:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
            combined_content.append(f"## Start of the file {file_path}\n\n```\n{file_content}\n```\n\n## End of {file_path}\n")
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
    return combined_content

def main():
    """Main function to collect and combine files."""
    starting_dir = os.getcwd()
    starting_dir = os.path.join(starting_dir, 'LocalYoutubeAIHelper-Python')
    files = collect_files(starting_dir)
    combined_content = combine_file_contents(files)
    output = "\n".join(combined_content)
    
    # Save to a new file
    output_file = "combined_files_for_llm.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(output)

    print(f"Combined content written to {output_file}")

if __name__ == "__main__":
    main()
