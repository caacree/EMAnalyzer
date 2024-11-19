import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re

def get_soup(url):
    response = requests.get(url)
    return BeautifulSoup(response.text, 'html.parser')

def parse_time(time_str):
    # Convert HH:MM:SS to total seconds
    try:
        h, m, s = map(int, time_str.split(':'))
        return h * 3600 + m * 60 + s
    except:
        return float('inf')

def get_2024_registrants():
    soup = get_soup('https://www.harpethhillsmarathon.com/Runners/registrants2024.html')
    registrants = []
    
    # Find the table with registrants
    table = soup.find('table')
    if table:
        rows = table.find_all('tr')[1:]  # Skip header row
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 2:
                name = cols[1].text.strip()
                registrants.append(name)
    
    return registrants

def get_previous_times(year):
    url = f'https://www.harpethhillsmarathon.com/Runners/finishers{year}.html'
    soup = get_soup(url)
    results = {}
    
    table = soup.find('table')
    if table:
        rows = table.find_all('tr')[1:]  # Skip header row
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 3:  # Ensure we have name and time columns
                name = cols[1].text.strip()
                time = cols[2].text.strip()
                if time:  # Only store if there's a valid time
                    results[name] = time
    
    return results

def main():
    # Get 2024 registrants
    registrants = get_2024_registrants()
    
    # Get previous years' results
    previous_results = {}
    for year in [2023, 2022, 2021]:
        previous_results[year] = get_previous_times(year)
    
    # Find best times for each 2024 registrant
    runner_times = {}
    for runner in registrants:
        best_time = float('inf')
        for year, results in previous_results.items():
            if runner in results:
                time_seconds = parse_time(results[runner])
                best_time = min(best_time, time_seconds)
        if best_time != float('inf'):
            runner_times[runner] = best_time
    
    # Sort runners by best time and get top 3
    sorted_runners = sorted(runner_times.items(), key=lambda x: x[1])
    
    print("\nTop 3 2024 Registrants by Previous Finishing Times:")
    print("================================================")
    for i, (runner, time) in enumerate(sorted_runners[:3], 1):
        hours = time // 3600
        minutes = (time % 3600) // 60
        seconds = time % 60
        print(f"{i}. {runner} - Best Time: {hours:02d}:{minutes:02d}:{seconds:02d}")

if __name__ == "__main__":
    main()
