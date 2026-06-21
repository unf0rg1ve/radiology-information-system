import React, { useEffect, useState } from 'react';
import { Alert, Button, Empty, Spin, Typography } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { dicomApi, ordersApi } from '../../api/client';

const { Text } = Typography;

interface DicomViewerProps {
  orderId?: string | null;
  height?: number | string;
}

export const DicomViewer: React.FC<DicomViewerProps> = ({ orderId, height = 560 }) => {
  const [viewerState, setViewerState] = useState<{
    url: string | null;
    loading: boolean;
    error: string | null;
  }>({ url: null, loading: false, error: null });

  const fetchViewerUrl = async () => {
    if (!orderId) {
      setViewerState({ url: null, loading: false, error: null });
      return;
    }

    setViewerState({ url: null, loading: true, error: null });
    try {
      const studyRes = await ordersApi.getStudy(orderId);
      const studyInstanceUid = studyRes.data?.study_instance_uid;
      if (!studyInstanceUid) {
        setViewerState({ url: null, loading: false, error: 'Снимки ещё не получены' });
        return;
      }

      const orthancStudyId = studyRes.data?.orthanc_study_id;
      const viewerRes = await dicomApi.getViewerUrl(studyInstanceUid, orthancStudyId);
      setViewerState({ url: viewerRes.data?.url || null, loading: false, error: null });
    } catch (err: any) {
      if (err.response?.status === 404) {
        setViewerState({ url: null, loading: false, error: 'Снимки ещё не получены' });
        return;
      }

      const detail = err.response?.data?.detail || 'Orthanc недоступен';
      setViewerState({ url: null, loading: false, error: detail });
    }
  };

  useEffect(() => {
    fetchViewerUrl();
  }, [orderId]);

  if (!orderId) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description="Выберите направление для просмотра снимков"
        style={{ margin: '24px 0' }}
      />
    );
  }

  return (
    <div>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 12,
        marginBottom: 8,
      }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          Stone Web Viewer · Orthanc
        </Text>
        <Button
          size="small"
          icon={<ReloadOutlined />}
          onClick={fetchViewerUrl}
          loading={viewerState.loading}
        >
          Обновить
        </Button>
      </div>

      {viewerState.loading && (
        <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Spin tip="Загрузка вьюера..." />
        </div>
      )}

      {viewerState.error && (
        <Alert message={viewerState.error} type="warning" showIcon style={{ marginBottom: 8 }} />
      )}

      {viewerState.url && !viewerState.loading && (
        <iframe
          src={viewerState.url}
          style={{
            width: '100%',
            height,
            border: '1px solid var(--c-border)',
            borderRadius: 4,
            background: '#000',
          }}
          title="DICOM Viewer"
          allow="fullscreen"
        />
      )}
    </div>
  );
};
