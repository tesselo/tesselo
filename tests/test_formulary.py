from classify.models import PredictedLayer
from django.test import TestCase
from formulary.models import Formula, PredictedLayerFormula


class FormularyTests(TestCase):

    def setUp(self):
        self.formula = Formula.objects.create(
            name='Formula',
            formula='B2/B3',
            min_val=-100,
            max_val=100,
        )

        self.predictedlayer = PredictedLayer.objects.create()

        self.predform = PredictedLayerFormula.objects.create(
            formula=self.formula,
            predictedlayer=self.predictedlayer,
            key='#bAnAnA23 *.*',
        )

    def test_predictedlayerformula_alphanum_key(self):
        self.assertEqual(self.predform.key, 'bAnAnA23')

    def test_colormap(self):
        self.assertEqual(
            self.formula.colormap,
            {
                '(-100.0<=x)&(x<-60.0)': [215, 25, 28, 255],
                '(-20.0<=x)&(x<20.0)': [255, 255, 191, 255],
                '(-60.0<=x)&(x<-20.0)': [253, 174, 97, 255],
                '(20.0<=x)&(x<60.0)': [166, 217, 106, 255],
                '(60.0<=x)&(x<100.0)': [26, 150, 65, 255],
            }
        )
