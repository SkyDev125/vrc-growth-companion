import json
from pathlib import Path
import unittest
from measurement_format import format_measurement

class MeasurementFormattingTests(unittest.TestCase):
    def test_shared_conversion_examples(self):
        examples = json.loads(Path(__file__).with_name('measurement-examples.json').read_text(encoding='utf-8'))
        for value, unit, expected in examples:
            with self.subTest(value=value, unit=unit):
                self.assertEqual(format_measurement(value, unit), expected)

if __name__ == '__main__':
    unittest.main()
