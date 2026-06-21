import { message } from 'antd';
import type { FormInstance } from 'antd';

interface ValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
}

function cleanMsg(msg: string): string {
  return msg.replace(/^Value error,\s*/i, '');
}

function getDetail(error: any): string | undefined {
  const detail = error.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail.map((e: ValidationError) => cleanMsg(e.msg)).join('; ');
  }
  return detail;
}

export function handleApiError(error: any, form?: FormInstance): void {
  console.error('API Error:', error.response?.data || error);

  const data = error.response?.data;

  if (error.response?.status === 422 && Array.isArray(data?.detail)) {
    if (form) {
      const fieldErrors = data.detail.map((e: ValidationError) => ({
        name: Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : 'iin',
        errors: [cleanMsg(e.msg)],
      }));
      form.setFields(fieldErrors);
      return;
    }
  }

  const detail = getDetail(error);
  if (!error.response) {
    message.error('Ошибка сети. Проверьте подключение к серверу.');
  } else if (error.response.status === 401) {
    return; // handled by interceptor
  } else if (error.response.status === 422) {
    message.warning(detail || 'Ошибка заполнения. Проверьте обязательные поля.');
  } else if (error.response.status === 403) {
    message.error(detail || 'У вас нет прав для выполнения этого действия.');
  } else if (error.response.status === 404) {
    message.error(detail || 'Запрашиваемый ресурс не найден.');
  } else if (error.response.status === 409) {
    message.warning(detail || 'Конфликт данных. Запись уже существует.');
  } else if (error.response.status >= 500) {
    message.error(detail || 'Ошибка сервера. Попробуйте позже или обратитесь к администратору.');
  } else {
    message.error(detail || 'Произошла ошибка. Попробуйте снова.');
  }
}
