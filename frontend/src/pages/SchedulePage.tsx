import React, { useState, useEffect } from 'react';
import { Card, Calendar, Badge, Select, Button, message, Spin, Typography, Modal, Form, DatePicker, Tag, Segmented, Space, Alert } from 'antd';
import { CalendarOutlined, ReloadOutlined, PlusOutlined, ArrowLeftOutlined, ArrowRightOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import dayjs, { Dayjs } from 'dayjs';
import 'dayjs/locale/ru';
import { refsApi, scheduleApi, ordersApi } from '../api/client';

const { Title, Text } = Typography;

const STATUS_COLORS: Record<string, string> = {
  NEW: '#1d4ed8',
  SCHEDULED: '#15803d',
  ARRIVED: '#0e7490',
  IN_PROGRESS: '#a16207',
  ACQUIRED: '#6d28d9',
  TO_REPORT: '#c2410c',
  REPORTING: '#1e40af',
  SIGNED: '#065f46',
  ISSUED: '#475569',
  CANCELLED: '#b91c1c',
};

export const SchedulePage: React.FC = () => {
  const { t } = useTranslation();
  const [devices, setDevices] = useState<any[]>([]);
  const [selectedDevice, setSelectedDevice] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'month' | 'week'>('week');
  const [weeklySlots, setWeeklySlots] = useState<Record<string, any[]>>({});
  const [monthSlots, setMonthSlots] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedDate, setSelectedDate] = useState(dayjs());
  const [weekStart, setWeekStart] = useState(dayjs().startOf('day'));
  const [orders, setOrders] = useState<any[]>([]);
  const [bookModal, setBookModal] = useState<{ open: boolean; slot: any }>({ open: false, slot: null });
  const [moveModal, setMoveModal] = useState<{ open: boolean; appointment: any; date: string; start: string; end: string } | null>(null);
  const [bookError, setBookError] = useState<string | null>(null);
  const [form] = Form.useForm();
  const today = dayjs().startOf('day');

  const disabledPastDate = (current: Dayjs) => current.isBefore(today, 'day');
  const isPastSlot = (slot: any) => dayjs(slot.end).isBefore(dayjs());
  const nextWeekStart = (date: Dayjs) => date.isBefore(today, 'day') ? today : date.startOf('day');

  useEffect(() => {
    const fetchDevices = async () => {
      try {
        const response = await refsApi.devices();
        const activeDevices = (response.data || []).filter((d: any) => d.status === 'ACTIVE');
        setDevices(activeDevices);
        if (activeDevices.length > 0 && !selectedDevice) {
          setSelectedDevice(activeDevices[0].id);
        }
      } catch (error) {
        message.error(t('common.error'));
      }
    };
    fetchDevices();
  }, []);

  const fetchSlots = async () => {
    if (!selectedDevice) return;
    setLoading(true);
    try {
      if (viewMode === 'month') {
        const response = await scheduleApi.slots({
          device_id: selectedDevice,
          date: selectedDate.format('YYYY-MM-DD'),
        });
        setMonthSlots(response.data?.slots || []);
      } else {
        const slotsByDay: Record<string, any[]> = {};
        const start = weekStart;
        for (let i = 0; i < 7; i++) {
          const date = start.add(i, 'day');
          const dateStr = date.format('YYYY-MM-DD');
          const response = await scheduleApi.slots({
            device_id: selectedDevice,
            date: dateStr,
          });
          slotsByDay[dateStr] = response.data?.slots || [];
        }
        setWeeklySlots(slotsByDay);
      }
    } catch (error) {
      message.error(t('common.error'));
    } finally {
      setLoading(false);
    }
  };

  const fetchOrders = async () => {
    try {
      const response = await ordersApi.list({ status: 'NEW', limit: 100 });
      setOrders(response.data || []);
    } catch (error) {
      console.error(error);
    }
  };

  useEffect(() => {
    fetchSlots();
  }, [selectedDevice, selectedDate, viewMode, weekStart]);

  useEffect(() => {
    fetchOrders();
  }, []);

  const handleBook = async (values: any) => {
    if (!bookModal.slot) return;
    setBookError(null);
    try {
      await scheduleApi.createAppointment({
        order_id: values.order_id,
        device_id: selectedDevice,
        slot_start: bookModal.slot.start,
        slot_end: bookModal.slot.end,
      });
      message.success(t('schedule.book') + 'ено');
      setBookModal({ open: false, slot: null });
      form.resetFields();
      fetchSlots();
      fetchOrders();
    } catch (error: any) {
      const detail = error.response?.data?.detail || t('common.error');
      if (typeof detail === 'string') {
        setBookError(detail);
      } else {
        message.error(t('common.error'));
      }
    }
  };

  const handleCancelSlot = async (appointmentId: string) => {
    try {
      await scheduleApi.cancelAppointment(appointmentId);
      message.success(t('schedule.cancel'));
      fetchSlots();
      fetchOrders();
    } catch (error: any) {
      message.error(error.response?.data?.detail || t('common.error'));
    }
  };

  const handleMove = async () => {
    if (!moveModal) return;
    try {
      await scheduleApi.updateAppointment(moveModal.appointment.id, {
        slot_start: `${moveModal.date}T${moveModal.start}`,
        slot_end: `${moveModal.date}T${moveModal.end}`,
      });
      message.success('Запись перенесена');
      setMoveModal(null);
      fetchSlots();
    } catch (error: any) {
      message.error(error.response?.data?.detail || t('common.error'));
    }
  };

  const getListData = (value: dayjs.Dayjs) => {
    const dateStr = value.format('YYYY-MM-DD');
    const daySlots = monthSlots.filter((s: any) => s.start.startsWith(dateStr));
    const occupiedCount = daySlots.filter((s: any) => s.occupied).length;
    const totalCount = daySlots.length;
    if (occupiedCount > 0) {
      return [{ type: 'success' as const, content: `${occupiedCount}/${totalCount}` }];
    }
    return [];
  };

  const dateCellRender = (value: dayjs.Dayjs) => {
    const listData = getListData(value);
    return (
      <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
        {listData.map((item, index) => (
          <li key={index}><Badge status={item.type} text={<span style={{ fontSize: 10 }}>{item.content}</span>} /></li>
        ))}
      </ul>
    );
  };

  const renderMonthView = () => {
    const selectedDateSlots = monthSlots.filter((s: any) => s.start.startsWith(selectedDate.format('YYYY-MM-DD')));
    return (
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 350px', gap: 16 }}>
        <Card>
            <Calendar
              value={selectedDate}
              onSelect={(date) => {
                if (!disabledPastDate(date)) setSelectedDate(date);
              }}
              disabledDate={disabledPastDate}
              cellRender={dateCellRender}
              mode="month"
            />
        </Card>

        <Card title={`${t('schedule.date')}: ${selectedDate.format('DD.MM.YYYY')}`} bodyStyle={{ padding: 0 }}>
          <Spin spinning={loading}>
            <div style={{ maxHeight: 500, overflow: 'auto' }}>
              {selectedDateSlots.map((slot: any, idx: number) => (
                <div key={idx} style={{
                  padding: '10px 16px', borderBottom: '1px solid var(--c-border)',
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  background: slot.occupied ? 'var(--s-sch-bg)' : 'transparent',
                  opacity: isPastSlot(slot) ? 0.55 : 1,
                }}>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600 }}>
                      {dayjs(slot.appointment?.slot_start || slot.start).format('HH:mm')} - {dayjs(slot.appointment?.slot_end || slot.end).format('HH:mm')}
                    </div>
                    {slot.occupied && slot.appointment && (
                      <div style={{ fontSize: 11, color: 'var(--c-text2)' }}>
                        {slot.appointment.accession_number || 'AN'} · {slot.appointment.patient_name || 'Пациент'}
                      </div>
                    )}
                  </div>
                  <div>
                    {slot.occupied ? (
                      <Button size="small" danger disabled={isPastSlot(slot)} onClick={() => handleCancelSlot(slot.appointment?.id)}>
                        {t('schedule.cancel')}
                      </Button>
                    ) : (
                      <Button size="small" type="primary" icon={<PlusOutlined />} disabled={isPastSlot(slot)}
                        onClick={() => setBookModal({ open: true, slot })}>
                        {t('schedule.book')}
                      </Button>
                    )}
                  </div>
                </div>
              ))}
              {selectedDateSlots.length === 0 && (
                <div style={{ padding: 40, textAlign: 'center', color: 'var(--c-text2)' }}>{t('common.noData')}</div>
              )}
            </div>
          </Spin>
        </Card>
      </div>
    );
  };

  const renderWeeklyView = () => {
    const days: Dayjs[] = Array.from({ length: 7 }, (_, i) => weekStart.add(i, 'day'));
    const dates = days.map(d => d.format('YYYY-MM-DD'));
    const allSlots = dates.flatMap(d => weeklySlots[d] || []);
    const uniqueTimes = Array.from(new Set(allSlots.map(s => dayjs(s.start).format('HH:mm')))).sort();

    return (
      <Card bodyStyle={{ padding: 12 }}>
        <Spin spinning={loading}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <Space>
              <Button
                icon={<ArrowLeftOutlined />}
                disabled={!weekStart.isAfter(today, 'day')}
                onClick={() => setWeekStart(nextWeekStart(weekStart.subtract(1, 'week')))}
              />
              <Text strong>{weekStart.format('DD.MM.YYYY')} — {weekStart.add(6, 'day').format('DD.MM.YYYY')}</Text>
              <Button icon={<ArrowRightOutlined />} onClick={() => setWeekStart(weekStart.add(1, 'week'))} />
            </Space>
            <Button icon={<ReloadOutlined />} onClick={fetchSlots} loading={loading}>{t('common.refresh')}</Button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '60px repeat(7, minmax(0, 1fr))', gap: 1, background: 'var(--c-border)', border: '1px solid var(--c-border)' }}>
            <div style={{ background: 'var(--c-surface2)', padding: 8, fontSize: 11, fontWeight: 700, textAlign: 'center' }}>Время</div>
            {days.map((d, i) => (
              <div key={i} style={{ background: 'var(--c-surface2)', padding: 8, textAlign: 'center' }}>
                <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'capitalize' }}>{d.locale('ru').format('dd')}</div>
                <div style={{ fontSize: 12 }}>{d.format('DD.MM')}</div>
              </div>
            ))}

            {uniqueTimes.length === 0 && (
              <div style={{ gridColumn: '1 / -1', background: 'var(--c-surface)', padding: 40, textAlign: 'center', color: 'var(--c-text2)' }}>
                {t('common.noData')}
              </div>
            )}

            {uniqueTimes.map(timeStr => (
              <React.Fragment key={timeStr}>
                <div style={{ background: 'var(--c-surface)', padding: 8, fontSize: 11, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{timeStr}</div>
                {dates.map(dateStr => {
                  const daySlots = weeklySlots[dateStr] || [];
                  const slot = daySlots.find((s: any) => dayjs(s.start).format('HH:mm') === timeStr);
                  if (!slot) {
                    return <div key={`${dateStr}-${timeStr}`} style={{ background: 'var(--c-surface)', minHeight: 48 }} />;
                  }
                  const orderStatus = slot.appointment?.order_status || 'SCHEDULED';
                  const color = STATUS_COLORS[orderStatus] || STATUS_COLORS.SCHEDULED;
                  const slotIsPast = isPastSlot(slot);
                  return (
                    <div key={`${dateStr}-${timeStr}`} style={{
                      background: slot.occupied ? `${color}15` : 'var(--c-surface)',
                      minHeight: 48,
                      padding: 4,
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'center',
                      alignItems: 'center',
                      fontSize: 11,
                      borderLeft: slot.occupied ? `3px solid ${color}` : 'none',
                      opacity: slotIsPast ? 0.55 : 1,
                    }}>
                      {slot.occupied ? (
                        <>
                          <Text style={{ maxWidth: '100%', fontSize: 10, fontWeight: 700 }}>
                            {dayjs(slot.appointment?.slot_start || slot.start).format('HH:mm')} - {dayjs(slot.appointment?.slot_end || slot.end).format('HH:mm')}
                          </Text>
                          <Text ellipsis style={{ maxWidth: '100%', fontSize: 10, fontWeight: 500 }}>
                            {slot.appointment?.patient_name || 'Пациент'}
                          </Text>
                          <Text type="secondary" ellipsis style={{ maxWidth: '100%', fontSize: 10 }}>
                            {slot.appointment?.accession_number || 'AN'}
                          </Text>
                          {!slotIsPast && (
                            <Space size={2}>
                              <Button size="small" type="text" style={{ fontSize: 10, padding: '0 4px' }} onClick={() => setMoveModal({
                                open: true,
                                appointment: slot.appointment,
                                date: dateStr,
                                start: dayjs(slot.appointment?.slot_start || slot.start).format('HH:mm'),
                                end: dayjs(slot.appointment?.slot_end || slot.end).format('HH:mm'),
                              })}>Перенести</Button>
                              <Button size="small" type="text" danger style={{ fontSize: 10, padding: '0 4px' }} onClick={() => handleCancelSlot(slot.appointment?.id)}>{t('schedule.cancel')}</Button>
                            </Space>
                          )}
                        </>
                      ) : (
                        slotIsPast ? (
                          <Text type="secondary" style={{ fontSize: 10 }}>Прошло</Text>
                        ) : (
                          <Button size="small" type="text" icon={<PlusOutlined />} style={{ fontSize: 10, padding: '0 4px' }} onClick={() => setBookModal({ open: true, slot })}>
                            {t('schedule.book')}
                          </Button>
                        )
                      )}
                    </div>
                  );
                })}
              </React.Fragment>
            ))}
          </div>
        </Spin>
      </Card>
    );
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0, color: 'var(--c-text)' }}>
          <CalendarOutlined style={{ marginRight: 8 }} />{t('nav.schedule')}
        </Title>
        <Space>
          <Select value={selectedDevice} onChange={setSelectedDevice} style={{ width: 280 }}
            placeholder={t('schedule.device')}
            options={devices.map((d: any) => ({ value: d.id, label: `${d.name} (${d.modality_type})` }))} />
          <Segmented
            value={viewMode}
            onChange={(v) => setViewMode(v as 'month' | 'week')}
            options={[
              { value: 'week', label: 'Неделя' },
              { value: 'month', label: 'Месяц' },
            ]}
          />
          {viewMode === 'month' && (
            <DatePicker value={selectedDate} onChange={(d) => d && setSelectedDate(d)} disabledDate={disabledPastDate} format="DD.MM.YYYY" />
          )}
          {viewMode === 'week' && (
            <DatePicker value={weekStart} onChange={(d) => d && setWeekStart(nextWeekStart(d))} disabledDate={disabledPastDate} format="DD.MM.YYYY" placeholder="Период с" />
          )}
        </Space>
      </div>

      {viewMode === 'month' ? renderMonthView() : renderWeeklyView()}

      <Modal title={t('schedule.book')} open={bookModal.open}
        onCancel={() => { setBookError(null); setBookModal({ open: false, slot: null }); form.resetFields(); }}
        onOk={() => form.submit()} width={500}>
        <Form form={form} layout="vertical" onFinish={handleBook}>
          {bookError && (
            <Alert message={bookError} type="warning" showIcon closable onClose={() => setBookError(null)} style={{ marginBottom: 12 }} />
          )}
          <Form.Item name="order_id" label={t('orders.title')} rules={[{ required: true }]}>
            <Select showSearch placeholder="Выберите направление (NEW)"
              options={orders.map((o: any) => ({
                value: o.id,
                label: `${o.accession_number} — ${o.patient_name} (${o.modality})`,
              }))} />
          </Form.Item>
          {bookModal.slot && (
            <Tag color="blue">{dayjs(bookModal.slot.start).format('HH:mm')} - {dayjs(bookModal.slot.end).format('HH:mm')}</Tag>
          )}
        </Form>
      </Modal>

      <Modal title="Перенести запись" open={moveModal?.open || false}
        onCancel={() => setMoveModal(null)}
        onOk={handleMove}>
        {moveModal && (
          <Form layout="vertical">
            <Form.Item label="Пациент">
              <Text strong>{moveModal.appointment.patient_name}</Text>
            </Form.Item>
            <Form.Item label="Новая дата">
              <DatePicker value={dayjs(moveModal.date)} onChange={(d) => d && setMoveModal({ ...moveModal, date: d.format('YYYY-MM-DD') })} disabledDate={disabledPastDate} format="DD.MM.YYYY" />
            </Form.Item>
            <Form.Item label="Новое время начала">
              <DatePicker.TimePicker value={dayjs(`2000-01-01T${moveModal.start}`)} onChange={(t) => t && setMoveModal({ ...moveModal, start: t.format('HH:mm') })} format="HH:mm" />
            </Form.Item>
            <Form.Item label="Новое время окончания">
              <DatePicker.TimePicker value={dayjs(`2000-01-01T${moveModal.end}`)} onChange={(t) => t && setMoveModal({ ...moveModal, end: t.format('HH:mm') })} format="HH:mm" />
            </Form.Item>
          </Form>
        )}
      </Modal>
    </div>
  );
};
