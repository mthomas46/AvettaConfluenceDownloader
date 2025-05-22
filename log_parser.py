import argparse
import re

def parse_log_line(line):
    # Example: 2024-07-01 12:34:56,789 [INFO] [LLM Combine] Message
    match = re.match(r'^(.*?) \[(.*?)\] \[(.*?)\] (.*)$', line)
    if match:
        timestamp, level, feature, message = match.groups()
        return {
            'timestamp': timestamp,
            'level': level,
            'feature': feature,
            'message': message,
            'raw': line
        }
    return None

def search_logs(logfile, level=None, feature=None, api=None, keyword=None):
    with open(logfile, 'r') as f:
        for line in f:
            parsed = parse_log_line(line)
            if not parsed:
                continue
            if level and parsed['level'].upper() != level.upper():
                continue
            if feature and feature.lower() not in parsed['feature'].lower():
                continue
            if api and api.lower() not in parsed['message'].lower():
                continue
            if keyword and keyword.lower() not in parsed['raw'].lower():
                continue
            print(parsed['raw'], end='')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Parse and search CLI logs.")
    parser.add_argument('logfile', help='Path to the log file')
    parser.add_argument('--level', help='Log level to filter (INFO, WARNING, ERROR, etc.)')
    parser.add_argument('--feature', help='Feature tag to filter (e.g., LLM Combine, Download)')
    parser.add_argument('--api', help='Search for API calls (e.g., JIRA, Confluence)')
    parser.add_argument('--keyword', help='Search for a keyword in the log message')
    args = parser.parse_args()

    search_logs(
        args.logfile,
        level=args.level,
        feature=args.feature,
        api=args.api,
        keyword=args.keyword
    ) 