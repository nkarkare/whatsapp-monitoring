#!/usr/bin/env python3
"""
Natural Date Parser

Extracts due dates from natural language text including:
- Explicit dates: "dec 5", "5th December", "2025-12-05"
- Relative dates: "tomorrow", "next week", "in 3 days"
- Day names: "monday", "next friday"
- Mixed language: Marathi + English date references
"""

import re
from datetime import datetime, timedelta
from typing import Optional
import calendar


class DateParser:
    """Parse natural language dates from mixed English/Marathi text"""

    # Month mappings
    MONTHS = {
        'jan': 1, 'january': 1,
        'feb': 2, 'february': 2,
        'mar': 3, 'march': 3,
        'apr': 4, 'april': 4,
        'may': 5,
        'jun': 6, 'june': 6,
        'jul': 7, 'july': 7,
        'aug': 8, 'august': 8,
        'sep': 9, 'sept': 9, 'september': 9,
        'oct': 10, 'october': 10,
        'nov': 11, 'november': 11,
        'dec': 12, 'december': 12
    }

    # Weekday mappings
    WEEKDAYS = {
        'monday': 0, 'mon': 0,
        'tuesday': 1, 'tue': 1, 'tues': 1,
        'wednesday': 2, 'wed': 2,
        'thursday': 3, 'thu': 3, 'thur': 3, 'thurs': 3,
        'friday': 4, 'fri': 4,
        'saturday': 5, 'sat': 5,
        'sunday': 6, 'sun': 6
    }

    # Marathi date words
    MARATHI_DATES = {
        'udya': 1,  # tomorrow
        'उद्या': 1,
        'parva': 2,  # day after tomorrow
        'परवा': 2,
        'aaj': 0,  # today
        'आज': 0
    }

    @staticmethod
    def parse_date(text: str) -> Optional[str]:
        """
        Parse date from natural language text

        Args:
            text: Text containing date reference

        Returns:
            Date in YYYY-MM-DD format or None
        """
        if not text:
            return None

        text_lower = text.lower()

        # Try different parsing strategies in order of specificity

        # 1. ISO format (YYYY-MM-DD)
        iso_match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', text)
        if iso_match:
            year, month, day = iso_match.groups()
            try:
                date = datetime(int(year), int(month), int(day))
                return date.strftime('%Y-%m-%d')
            except ValueError:
                pass

        # 2. Month + Day (e.g., "dec 5", "december 5th", "5 dec")
        month_day = DateParser._parse_month_day(text_lower)
        if month_day:
            return month_day

        # 3. Day/Month format (e.g., "5/12", "05/12")
        dm_match = re.search(r'(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?', text)
        if dm_match:
            day, month, year = dm_match.groups()
            try:
                year = int(year) if year else datetime.now().year
                if year < 100:  # Two-digit year
                    year += 2000
                date = datetime(year, int(month), int(day))
                return date.strftime('%Y-%m-%d')
            except ValueError:
                pass

        # 4. Relative dates (today, tomorrow, etc.)
        relative = DateParser._parse_relative_date(text_lower)
        if relative:
            return relative

        # 5. Weekday names (monday, next friday, etc.)
        weekday = DateParser._parse_weekday(text_lower)
        if weekday:
            return weekday

        # 6. Marathi date words
        marathi = DateParser._parse_marathi_date(text_lower)
        if marathi:
            return marathi

        # 7. "In X days/weeks"
        in_days = DateParser._parse_in_duration(text_lower)
        if in_days:
            return in_days

        return None

    @staticmethod
    def _parse_month_day(text: str) -> Optional[str]:
        """Parse month + day patterns"""
        # Pattern: month day (e.g., "dec 5", "december 5th")
        for month_name, month_num in DateParser.MONTHS.items():
            pattern = rf'{month_name}\s+(\d{{1,2}})(?:st|nd|rd|th)?'
            match = re.search(pattern, text)
            if match:
                day = int(match.group(1))
                year = datetime.now().year
                try:
                    date = datetime(year, month_num, day)
                    # If date is in the past, assume next year
                    if date < datetime.now():
                        date = datetime(year + 1, month_num, day)
                    return date.strftime('%Y-%m-%d')
                except ValueError:
                    pass

        # Pattern: day month (e.g., "5 dec", "5th december")
        for month_name, month_num in DateParser.MONTHS.items():
            pattern = rf'(\d{{1,2}})(?:st|nd|rd|th)?\s+{month_name}'
            match = re.search(pattern, text)
            if match:
                day = int(match.group(1))
                year = datetime.now().year
                try:
                    date = datetime(year, month_num, day)
                    if date < datetime.now():
                        date = datetime(year + 1, month_num, day)
                    return date.strftime('%Y-%m-%d')
                except ValueError:
                    pass

        return None

    @staticmethod
    def _parse_relative_date(text: str) -> Optional[str]:
        """Parse relative date expressions"""
        today = datetime.now()

        # Today
        if 'today' in text or 'aaj' in text or 'आज' in text:
            return today.strftime('%Y-%m-%d')

        # Tomorrow
        if 'tomorrow' in text or 'tmrw' in text or 'tommorow' in text:
            return (today + timedelta(days=1)).strftime('%Y-%m-%d')

        # Day after tomorrow
        if 'day after tomorrow' in text or 'parva' in text or 'परवा' in text:
            return (today + timedelta(days=2)).strftime('%Y-%m-%d')

        # Next week
        if 'next week' in text:
            return (today + timedelta(days=7)).strftime('%Y-%m-%d')

        # This week
        if 'this week' in text:
            # End of week (Friday)
            days_until_friday = (4 - today.weekday()) % 7
            return (today + timedelta(days=days_until_friday)).strftime('%Y-%m-%d')

        # Next month
        if 'next month' in text:
            return (today + timedelta(days=30)).strftime('%Y-%m-%d')

        return None

    @staticmethod
    def _parse_weekday(text: str) -> Optional[str]:
        """Parse weekday names"""
        today = datetime.now()
        current_weekday = today.weekday()

        for day_name, target_weekday in DateParser.WEEKDAYS.items():
            if day_name in text:
                # Check if "next" is mentioned
                is_next = 'next' in text[:text.index(day_name)]

                # Calculate days until target weekday
                days_ahead = target_weekday - current_weekday
                if days_ahead <= 0 or is_next:
                    days_ahead += 7

                target_date = today + timedelta(days=days_ahead)
                return target_date.strftime('%Y-%m-%d')

        return None

    @staticmethod
    def _parse_marathi_date(text: str) -> Optional[str]:
        """Parse Marathi date expressions"""
        today = datetime.now()

        for marathi_word, days_offset in DateParser.MARATHI_DATES.items():
            if marathi_word in text:
                target_date = today + timedelta(days=days_offset)
                return target_date.strftime('%Y-%m-%d')

        return None

    @staticmethod
    def _parse_in_duration(text: str) -> Optional[str]:
        """Parse 'in X days/weeks' patterns"""
        today = datetime.now()

        # In X days
        match = re.search(r'in\s+(\d+)\s+days?', text)
        if match:
            days = int(match.group(1))
            return (today + timedelta(days=days)).strftime('%Y-%m-%d')

        # In X weeks
        match = re.search(r'in\s+(\d+)\s+weeks?', text)
        if match:
            weeks = int(match.group(1))
            return (today + timedelta(weeks=weeks)).strftime('%Y-%m-%d')

        # In X months (approximate)
        match = re.search(r'in\s+(\d+)\s+months?', text)
        if match:
            months = int(match.group(1))
            return (today + timedelta(days=months * 30)).strftime('%Y-%m-%d')

        return None

    @staticmethod
    def extract_all_dates(text: str) -> list:
        """
        Extract all potential dates from text

        Args:
            text: Text to search

        Returns:
            List of dates in YYYY-MM-DD format
        """
        dates = []

        # Try to find all date patterns
        # This is useful if message mentions multiple dates

        # ISO format dates
        iso_matches = re.findall(r'(\d{4})-(\d{1,2})-(\d{1,2})', text)
        for year, month, day in iso_matches:
            try:
                date = datetime(int(year), int(month), int(day))
                dates.append(date.strftime('%Y-%m-%d'))
            except ValueError:
                pass

        # Month + day patterns
        for month_name, month_num in DateParser.MONTHS.items():
            matches = re.finditer(rf'{month_name}\s+(\d{{1,2}})(?:st|nd|rd|th)?', text.lower())
            for match in matches:
                day = int(match.group(1))
                year = datetime.now().year
                try:
                    date = datetime(year, month_num, day)
                    if date < datetime.now():
                        date = datetime(year + 1, month_num, day)
                    dates.append(date.strftime('%Y-%m-%d'))
                except ValueError:
                    pass

        return dates


def parse_date(text: str) -> Optional[str]:
    """
    Convenience function to parse a single date from text

    Args:
        text: Text containing date

    Returns:
        Date in YYYY-MM-DD format or None
    """
    return DateParser.parse_date(text)


def extract_all_dates(text: str) -> list:
    """
    Convenience function to extract all dates from text

    Args:
        text: Text to search

    Returns:
        List of dates in YYYY-MM-DD format
    """
    return DateParser.extract_all_dates(text)
