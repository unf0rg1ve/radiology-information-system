import React, { useEffect, useState } from 'react';
import { Button, Descriptions, Space, Typography } from 'antd';
import { ArrowLeftOutlined, FileTextOutlined } from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { ordersApi } from '../api/client';
import { DicomViewer } from '../components/dicom/DicomViewer';
import { useAuthStore } from '../stores/authStore';

const { Title, Text } = Typography;

export const DicomViewerPage: React.FC = () => {
  const { orderId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'ADMIN';
  const [orderInfo, setOrderInfo] = useState<any>(null);

  useEffect(() => {
    const loadOrder = async () => {
      if (!orderId) return;
      try {
        const res = await ordersApi.get(orderId);
        setOrderInfo(res.data || null);
      } catch {
        setOrderInfo(null);
      }
    };
    loadOrder();
  }, [orderId]);

  return (
    <div>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 16,
        marginBottom: 16,
      }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>
            Назад
          </Button>
          <div>
            <Title level={4} style={{ margin: 0, color: 'var(--c-text)' }}>
              Просмотр снимков
            </Title>
            <Text type="secondary">
              {orderInfo?.accession_number || 'Направление'} · {orderInfo?.patient_name || 'Пациент'}
            </Text>
          </div>
        </Space>
        {orderId && !isAdmin && (
          <Button
            type="primary"
            icon={<FileTextOutlined />}
            onClick={() => navigate(`/reports/new?order_id=${orderId}`)}
          >
            Описание
          </Button>
        )}
      </div>

      {orderInfo && (
        <Descriptions
          size="small"
          column={{ xs: 1, sm: 2, lg: 4 }}
          style={{ marginBottom: 12 }}
        >
          <Descriptions.Item label="AN">{orderInfo.accession_number || '—'}</Descriptions.Item>
          <Descriptions.Item label="Пациент">{orderInfo.patient_name || '—'}</Descriptions.Item>
          <Descriptions.Item label="Услуга">{orderInfo.service_name || '—'}</Descriptions.Item>
          <Descriptions.Item label="Модальность">{orderInfo.modality || '—'}</Descriptions.Item>
        </Descriptions>
      )}

      <DicomViewer orderId={orderId} height="calc(100vh - 220px)" />
    </div>
  );
};
