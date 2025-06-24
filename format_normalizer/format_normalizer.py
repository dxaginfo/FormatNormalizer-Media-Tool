"""
FormatNormalizer Core Implementation

Python tool for normalizing media formats using FFmpeg with Gemini AI support.
"""
import ffmpeg
import os

class FormatNormalizer:
    def __init__(self, ai_integration=None):
        self.ai = ai_integration
    
    def convert(self, source_path, target_path, target_format, codec=None, preset='web', options=None):
        try:
            input_stream = ffmpeg.input(source_path)
            output_params = {}
            if codec:
                output_params['c:v'] = codec
            if preset:
                output_params['preset'] = preset
            ffmpeg.output(input_stream, target_path, **output_params).run()
            return {'success': True, 'output': target_path}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def analyze_content(self, file_path):
        if self.ai:
            return self.ai.analyze(file_path)
        return {'ai': 'not enabled'}
    
    def batch_convert(self, files, target_format, **kwargs):
        results = []
        for file in files:
            target_path = f"{os.path.splitext(file)[0]}.{target_format}"
            result = self.convert(file, target_path, target_format, **kwargs)
            results.append(result)
        return results
