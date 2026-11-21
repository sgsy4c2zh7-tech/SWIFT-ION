from pathlib import Path
from animation_format import check_animation
if __name__=='__main__':
    print('Animation validated:',check_animation(Path(__file__).resolve().parents[1]/'docs/animation',expected_min_frames=193))
