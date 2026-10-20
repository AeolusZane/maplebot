import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
import numpy as np
from src.utils.monster_name_learning import NameLearner
from src.utils.monster_names import template


class LearningTests(unittest.TestCase):
    def test_three_separated_agreements_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as root:
            learner=NameLearner(root)
            image=np.repeat(template('石膏犬')[:,:,None],3,axis=2)
            self.assertFalse(learner.accept('测试怪',image,'等级44测试怪',.99,0))
            self.assertFalse(learner.accept('测试怪',image,'等级44测试怪',.99,3))
            self.assertTrue(learner.accept('测试怪',image,'等级44测试怪',.99,6))
            path=Path(root)/'测试怪.png';before=path.read_bytes()
            self.assertFalse(learner.accept('测试怪',255-image,'等级44测试怪',.99,9))
            self.assertEqual(before,path.read_bytes())

    def test_wrong_text_low_confidence_and_unstable_image_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            learner=NameLearner(root);image=np.repeat(template('石膏犬')[:,:,None],3,axis=2)
            for text,confidence in [('等级44人物',.99),('等级44测试怪',.8)]:
                self.assertFalse(learner.accept('测试怪',image,text,confidence,0))
            for i in range(3):
                self.assertFalse(learner.accept('测试怪',image if i%2 else 255-image,'等级44测试怪',.99,i*3))
            self.assertFalse((Path(root)/'测试怪.png').exists())

    def test_ocr_requires_unique_complete_name(self):
        learner=NameLearner();box=[[0,0],[90,0],[90,36],[0,36]]
        learner.engine=Mock(return_value=([[box,'等级44测试怪',.99]],None))
        image=np.ones((20,40,3),np.uint8)*255
        self.assertIsNotNone(learner.read(image,'测试怪',1))
        self.assertIsNone(learner.read(image,'另一怪',1))
        learner.engine.return_value=([[box,'等级44测试怪',.99]]*2,None)
        self.assertIsNone(learner.read(image,'测试怪',1))

if __name__=='__main__':unittest.main()
