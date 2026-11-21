import tempfile,sys,json,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from animation_format import create_animation,check_animation
class AnimationFormatTest(unittest.TestCase):
    def fixture(self):
        t=datetime(2026,11,21,0,tzinfo=timezone.utc)
        times=[(t+timedelta(minutes=30*i)).isoformat() for i in range(6)]
        lat=[-20,0,20];lon=[-90,0,90]
        values=[[i+10]*9 for i in range(6)]
        return times,lat,lon,values
    def test_chunks_and_validation(self):
        with tempfile.TemporaryDirectory() as d:
            t,a,b,v=self.fixture()
            idx=create_animation(d,t,a,b,v,generated_at=t[0],chunk_size=2)
            self.assertEqual(len(idx['chunks']),3)
            self.assertEqual(check_animation(d,expected_min_frames=6)['frames'],6)
    def test_spacing_failure(self):
        with tempfile.TemporaryDirectory() as d:
            t,a,b,v=self.fixture();t[1]=t[0]
            with self.assertRaises(ValueError):create_animation(d,t,a,b,v,generated_at=t[0])
    def test_invalid_density_fails(self):
        with tempfile.TemporaryDirectory() as d:
            t,a,b,v=self.fixture();v[0][0]=-2
            with self.assertRaises(ValueError):create_animation(d,t,a,b,v,generated_at=t[0])
    def test_missing_chunk_fails(self):
        with tempfile.TemporaryDirectory() as d:
            t,a,b,v=self.fixture();create_animation(d,t,a,b,v,generated_at=t[0]);(Path(d)/'frames_000.json').unlink()
            with self.assertRaises(FileNotFoundError):check_animation(d,expected_min_frames=6)
if __name__=='__main__':unittest.main()
