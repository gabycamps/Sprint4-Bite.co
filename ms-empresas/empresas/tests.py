from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
import uuid

from .models import Empresa, Proyecto


class EmpresaModelTest(TestCase):
    def test_crear_empresa(self):
        empresa = Empresa.objects.create(
            nombre='Acme Corp',
            nit_o_rut='900123456-7',
        )
        self.assertIsInstance(empresa.id, uuid.UUID)
        self.assertEqual(empresa.estado, Empresa.Estado.ACTIVO)

    def test_nombre_unico(self):
        Empresa.objects.create(nombre='Duplicada', nit_o_rut='111')
        with self.assertRaises(Exception):
            Empresa.objects.create(nombre='Duplicada', nit_o_rut='222')


class ProyectoModelTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre='Test Corp',
            nit_o_rut='000-test',
        )

    def test_crear_proyecto(self):
        proyecto = Proyecto.objects.create(
            empresa=self.empresa,
            nombre='Proyecto Alpha',
            presupuesto='15000.00',
            cloud_account_id='aws-123',
        )
        self.assertIsInstance(proyecto.id, uuid.UUID)
        self.assertEqual(proyecto.estado, Proyecto.Estado.ACTIVO)

    def test_empresa_protegida(self):
        Proyecto.objects.create(
            empresa=self.empresa,
            nombre='P1',
            presupuesto='1000',
            cloud_account_id='x',
        )
        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):
            self.empresa.delete()


class ProyectosBatchTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='123')
        self.client.force_authenticate(user=self.user)
        self.empresa = Empresa.objects.create(
            nombre='Batch Corp',
            nit_o_rut='batch-001',
        )
        self.p1 = Proyecto.objects.create(
            empresa=self.empresa, nombre='P1',
            presupuesto='1000', cloud_account_id='c1',
            estado=Proyecto.Estado.ACTIVO,
        )
        self.p2 = Proyecto.objects.create(
            empresa=self.empresa, nombre='P2',
            presupuesto='2000', cloud_account_id='c2',
            estado=Proyecto.Estado.INACTIVO,
        )

    def test_batch_retorna_proyectos_validos(self):
        ids = f'{self.p1.id},{self.p2.id}'
        response = self.client.get(f'/api/v1/internal/proyectos/batch/?ids={ids}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_batch_solo_activos(self):
        ids = f'{self.p1.id},{self.p2.id}'
        response = self.client.get(f'/api/v1/internal/proyectos/batch/?ids={ids}&solo_activos=true')
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['proyectos'][0]['id'], str(self.p1.id))

    def test_batch_uuid_inexistente_se_omite(self):
        fake_id = uuid.uuid4()
        response = self.client.get(f'/api/v1/internal/proyectos/batch/?ids={self.p1.id},{fake_id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_batch_sin_ids_retorna_400(self):
        response = self.client.get('/api/v1/internal/proyectos/batch/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
