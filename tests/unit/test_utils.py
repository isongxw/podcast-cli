#!/usr/bin/env python3
"""
工具函数测试
"""

import tempfile
from pathlib import Path

import pytest

from src.utils import (
    sanitize_filename,
    get_file_extension,
    format_duration,
    calculate_file_hash,
    ProgressTracker,
    retry,
)


class TestSanitizeFilename:
    """文件名清理测试"""

    def test_basic_sanitize(self):
        assert sanitize_filename("test file") == "test file"
        assert sanitize_filename("test/file") == "test_file"

    def test_remove_illegal_chars(self):
        result = sanitize_filename('<test>:file|"name"*?')
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert '"' not in result
        assert "/" not in result
        assert "\\" not in result
        assert "|" not in result
        assert "?" not in result
        assert "*" not in result

    def test_special_chars_become_underscore(self):
        result = sanitize_filename("<<<<")
        assert "_" in result

    def test_max_length(self):
        long_name = "a" * 150
        result = sanitize_filename(long_name)
        assert len(result) == 100

    def test_strip_whitespace(self):
        assert sanitize_filename("  test  ") == "test"


class TestGetFileExtension:
    """文件扩展名测试"""

    def test_mp3(self):
        assert get_file_extension("https://example.com/audio.mp3") == ".mp3"

    def test_m4a(self):
        assert get_file_extension("https://example.com/audio.m4a") == ".m4a"

    def test_case_insensitive(self):
        assert get_file_extension("https://example.com/audio.MP3") == ".mp3"
        assert get_file_extension("https://example.com/audio.M4A") == ".m4a"

    def test_unknown_extension(self):
        assert get_file_extension("https://example.com/audio.unknown") == ".mp3"

    def test_no_extension(self):
        assert get_file_extension("https://example.com/audio") == ".mp3"

    def test_custom_formats(self):
        assert (
            get_file_extension("https://example.com/audio.flac", [".flac", ".wav"])
            == ".flac"
        )


class TestFormatDuration:
    """时长格式化测试"""

    def test_seconds_only(self):
        assert format_duration(30) == "00:30"
        assert format_duration(5) == "00:05"

    def test_minutes_and_seconds(self):
        assert format_duration(90) == "01:30"
        assert format_duration(125) == "02:05"

    def test_hours(self):
        assert format_duration(3661) == "1:01:01"
        assert format_duration(7200) == "2:00:00"

    def test_zero(self):
        assert format_duration(0) == "00:00"


class TestCalculateFileHash:
    """文件哈希测试"""

    def test_calculate_sha256(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test content")
            f.flush()

            hash_value = calculate_file_hash(Path(f.name), "sha256")
            assert len(hash_value) == 64
            assert hash_value.isalnum()

    def test_different_content(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f1:
            f1.write("content 1")
            f1.flush()

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f2:
            f2.write("content 2")
            f2.flush()

        hash1 = calculate_file_hash(Path(f1.name), "sha256")
        hash2 = calculate_file_hash(Path(f2.name), "sha256")

        assert hash1 != hash2


class TestProgressTracker:
    """进度追踪测试"""

    def test_init(self):
        tracker = ProgressTracker("测试任务")
        assert tracker.description == "测试任务"
        assert tracker.total_items == 0
        assert tracker.completed_items == 0

    def test_start(self):
        tracker = ProgressTracker("测试任务")
        tracker.start(10)
        assert tracker.total_items == 10
        assert tracker.start_time is not None

    def test_update(self):
        tracker = ProgressTracker("测试任务")
        tracker.start(10)
        tracker.update(5)
        assert tracker.completed_items == 5

    def test_summary(self):
        tracker = ProgressTracker("测试任务")
        tracker.start(10)
        tracker.update(10)
        summary = tracker.summary()
        assert "完成" in summary


class TestRetryDecorator:
    """重试装饰器测试"""

    def test_success_first_attempt(self):
        call_count = 0

        @retry(max_retries=3, delay=0.1)
        def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = success_func()
        assert result == "success"
        assert call_count == 1

    def test_retry_on_failure(self):
        call_count = 0

        @retry(max_retries=3, delay=0.1)
        def fail_twice_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"

        result = fail_twice_func()
        assert result == "success"
        assert call_count == 3

    def test_max_retries_exceeded(self):
        call_count = 0

        @retry(max_retries=2, delay=0.1)
        def always_fail_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        with pytest.raises(ValueError):
            always_fail_func()

        assert call_count == 3

    def test_specific_exception(self):
        call_count = 0

        @retry(max_retries=2, delay=0.1, exceptions=(ValueError,))
        def handle_value_error():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Retry me")
            return "success"

        @retry(max_retries=2, delay=0.1, exceptions=(ValueError,))
        def handle_type_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("Don't retry me")

        result = handle_value_error()
        assert result == "success"

        with pytest.raises(TypeError):
            handle_type_error()
