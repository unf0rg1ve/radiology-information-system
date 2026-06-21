import React, { useState, useCallback, useRef } from 'react';
import {
  Card, Select, Button, Input, Checkbox, Space, Tag, Typography,
  Row, Col, Modal, Form, Radio,
} from 'antd';
import {
  HolderOutlined, PlusOutlined, EditOutlined, DeleteOutlined,
  EyeOutlined, EyeInvisibleOutlined,
} from '@ant-design/icons';

const { Text, Title } = Typography;

export interface FieldDefinition {
  field_key: string;
  label_ru: string;
  type: 'text' | 'textarea' | 'number' | 'select' | 'checkbox' | 'radio';
  required?: boolean;
  options?: { label: string; value: string }[];
  default_value?: string | number | boolean;
}

interface FieldConstructorProps {
  value?: FieldDefinition[];
  onChange?: (fields: FieldDefinition[]) => void;
}

const FIELD_TYPES = [
  { value: 'text', label: 'Text' },
  { value: 'textarea', label: 'Textarea' },
  { value: 'number', label: 'Number' },
  { value: 'select', label: 'Select' },
  { value: 'checkbox', label: 'Checkbox' },
  { value: 'radio', label: 'Radio' },
];

function generateKey(label: string): string {
  return label
    .toLowerCase()
    .replace(/[^a-zа-яё0-9]+/g, '_')
    .replace(/^_|_$/g, '') || `field_${Date.now()}`;
}

const TYPE_BADGE_COLORS: Record<string, string> = {
  text: 'default',
  textarea: 'blue',
  number: 'gold',
  select: 'purple',
  checkbox: 'green',
  radio: 'cyan',
};

export const FieldConstructor: React.FC<FieldConstructorProps> = ({ value = [], onChange }) => {
  const [preview, setPreview] = useState(false);
  const [editIndex, setEditIndex] = useState<number | null>(null);
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const dragNode = useRef<HTMLElement | null>(null);

  const handleDragStart = useCallback((e: React.DragEvent, idx: number) => {
    dragNode.current = e.target as HTMLElement;
    setDragIndex(idx);
    e.dataTransfer.effectAllowed = 'move';
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent, idx: number) => {
    e.preventDefault();
    if (dragIndex === null || dragIndex === idx) return;
    const items = [...value];
    const item = items.splice(dragIndex, 1)[0];
    items.splice(idx, 0, item);
    onChange?.(items);
    setDragIndex(idx);
  }, [dragIndex, value, onChange]);

  const handleDragEnd = useCallback(() => {
    setDragIndex(null);
    dragNode.current = null;
  }, []);

  const handleAddField = (type: string) => {
    const baseLabel = FIELD_TYPES.find(f => f.value === type)?.label || type;
    const newField: FieldDefinition = {
      field_key: generateKey(baseLabel),
      label_ru: baseLabel,
      type: type as FieldDefinition['type'],
      required: false,
      options: type === 'select' || type === 'radio' ? [{ label: 'Вариант 1', value: 'option_1' }] : undefined,
    };
    onChange?.([...value, newField]);
    setEditIndex(value.length);
  };

  const handleDelete = (idx: number) => {
    const items = value.filter((_, i) => i !== idx);
    onChange?.(items);
    if (editIndex === idx) setEditIndex(null);
  };

  const handleEditSave = (field: FieldDefinition) => {
    if (editIndex === null) return;
    const items = [...value];
    items[editIndex] = field;
    onChange?.(items);
    setEditIndex(null);
  };

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 12 }}>
        <Col>
          <Space>
            <Button size="small" icon={<PlusOutlined />}>
              Добавить поле
              <Select
                variant="borderless"
                style={{ width: 0, padding: 0, marginLeft: 4 }}
                popupMatchSelectWidth={false}
                onChange={handleAddField}
                options={FIELD_TYPES}
                onClick={(e) => e.stopPropagation()}
              />
            </Button>
          </Space>
        </Col>
        <Col>
          <Button
            size="small"
            icon={preview ? <EyeInvisibleOutlined /> : <EyeOutlined />}
            onClick={() => setPreview(!preview)}
          >
            {preview ? 'Редактор' : 'Предпросмотр'}
          </Button>
        </Col>
      </Row>

      {value.length === 0 ? (
        <div style={{ padding: 24, textAlign: 'center', color: '#999', border: '1px dashed #d9d9d9', borderRadius: 8 }}>
          <Text type="secondary">Нет полей. Нажмите «Добавить поле», чтобы начать.</Text>
        </div>
      ) : preview ? (
        <PreviewPanel fields={value} />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {value.map((field, idx) => (
            <Card
              key={idx}
              size="small"
              style={{
                cursor: dragIndex === idx ? 'grabbing' : 'default',
                opacity: dragIndex === idx ? 0.5 : 1,
                borderLeft: `3px solid ${TYPE_BADGE_COLORS[field.type] === 'default' ? '#d9d9d9' : `var(--ant-${TYPE_BADGE_COLORS[field.type]})`}`,
              }}
              draggable
              onDragStart={(e) => handleDragStart(e, idx)}
              onDragOver={(e) => handleDragOver(e, idx)}
              onDragEnd={handleDragEnd}
            >
              <Row align="middle" gutter={8}>
                <Col>
                  <HolderOutlined style={{ cursor: 'grab', color: '#bbb', fontSize: 16 }} />
                </Col>
                <Col flex="auto">
                  <Space size={4}>
                    <Tag color={TYPE_BADGE_COLORS[field.type] || 'default'} style={{ margin: 0 }}>
                      {field.type}
                    </Tag>
                    <Text strong style={{ fontSize: 13 }}>{field.label_ru}</Text>
                    <Text type="secondary" style={{ fontSize: 11, fontFamily: 'monospace' }}>
                      {field.field_key}
                    </Text>
                    {field.required && <Tag color="red" style={{ margin: 0, fontSize: 10 }}>Обязательное</Tag>}
                  </Space>
                </Col>
                <Col>
                  <Space size={0}>
                    <Button type="text" size="small" icon={<EditOutlined />} onClick={() => setEditIndex(idx)} />
                    <Button type="text" size="small" icon={<DeleteOutlined />} danger onClick={() => handleDelete(idx)} />
                  </Space>
                </Col>
              </Row>
            </Card>
          ))}
        </div>
      )}

      <FieldEditorModal
        field={editIndex !== null ? value[editIndex] : null}
        onSave={handleEditSave}
        onCancel={() => setEditIndex(null)}
      />
    </div>
  );
};

interface EditorModalProps {
  field: FieldDefinition | null;
  onSave: (field: FieldDefinition) => void;
  onCancel: () => void;
}

const FieldEditorModal: React.FC<EditorModalProps> = ({ field, onSave, onCancel }) => {
  const [form] = Form.useForm();
  const [fieldType, setFieldType] = useState<string>('text');

  React.useEffect(() => {
    if (field) {
      form.setFieldsValue(field);
      setFieldType(field.type);
    }
  }, [field, form]);

  if (!field) return null;

  const handleOk = async () => {
    const values = await form.validateFields();
    onSave({
      ...field,
      ...values,
      type: fieldType as FieldDefinition['type'],
    });
  };

  return (
    <Modal
      title="Редактировать поле"
      open={!!field}
      onOk={handleOk}
      onCancel={onCancel}
      width={500}
      destroyOnClose
    >
      <Form form={form} layout="vertical" initialValues={field}>
        <Form.Item name="label_ru" label="Название" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item name="field_key" label="Ключ" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item label="Тип">
          <Select value={fieldType} onChange={setFieldType} options={FIELD_TYPES} />
        </Form.Item>
        <Form.Item name="required" label=" " valuePropName="checked">
          <Checkbox>Обязательное поле</Checkbox>
        </Form.Item>
        {(fieldType === 'select' || fieldType === 'radio') && (
          <Form.Item label="Варианты">
            <Form.Item name="options" noStyle>
              <OptionsEditor />
            </Form.Item>
          </Form.Item>
        )}
      </Form>
    </Modal>
  );
};

const OptionsEditor: React.FC<{ value?: { label: string; value: string }[]; onChange?: (v: { label: string; value: string }[]) => void }> = ({ value = [], onChange }) => {
  const addOption = () => {
    onChange?.([...value, { label: `Вариант ${value.length + 1}`, value: `option_${value.length + 1}` }]);
  };

  const updateOption = (idx: number, key: 'label' | 'value', val: string) => {
    const items = [...value];
    items[idx] = { ...items[idx], [key]: val };
    onChange?.(items);
  };

  const removeOption = (idx: number) => {
    onChange?.(value.filter((_, i) => i !== idx));
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {value.map((opt, idx) => (
        <Row key={idx} gutter={8} align="middle">
          <Col span={8}>
            <Input size="small" value={opt.label} placeholder="Метка" onChange={(e) => updateOption(idx, 'label', e.target.value)} />
          </Col>
          <Col span={8}>
            <Input size="small" value={opt.value} placeholder="Значение" onChange={(e) => updateOption(idx, 'value', e.target.value)} />
          </Col>
          <Col>
            <Button type="text" size="small" icon={<DeleteOutlined />} danger onClick={() => removeOption(idx)} />
          </Col>
        </Row>
      ))}
      <Button size="small" icon={<PlusOutlined />} onClick={addOption}>
        Добавить вариант
      </Button>
    </div>
  );
};

const PreviewPanel: React.FC<{ fields: FieldDefinition[] }> = ({ fields }) => (
  <div style={{ padding: 16, border: '1px solid #d9d9d9', borderRadius: 8, background: '#fafafa' }}>
    <Title level={5} style={{ marginTop: 0, marginBottom: 16 }}>Предпросмотр шаблона</Title>
    {fields.map((field, idx) => (
      <div key={idx} style={{ marginBottom: 12 }}>
        <Text style={{ display: 'block', marginBottom: 4, fontWeight: 500 }}>
          {field.label_ru}
          {field.required && <Text type="danger"> *</Text>}
        </Text>
        {field.type === 'text' && <Input placeholder={field.label_ru} />}
        {field.type === 'textarea' && <Input.TextArea rows={2} placeholder={field.label_ru} />}
        {field.type === 'number' && <Input type="number" placeholder="0" style={{ width: 120 }} />}
        {field.type === 'select' && (
          <Select placeholder={field.label_ru} style={{ width: '100%' }}
            options={field.options?.map(o => ({ value: o.value, label: o.label }))} />
        )}
        {field.type === 'checkbox' && <Checkbox>{field.label_ru}</Checkbox>}
        {field.type === 'radio' && (
          <Radio.Group>
            {field.options?.map((o, i) => <Radio key={i} value={o.value}>{o.label}</Radio>)}
          </Radio.Group>
        )}
      </div>
    ))}
  </div>
);
