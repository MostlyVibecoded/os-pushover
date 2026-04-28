<?php

namespace OPNsense\Pushover\Api;

use OPNsense\Base\ApiMutableServiceControllerBase;
use OPNsense\Core\Backend;

class ServiceController extends ApiMutableServiceControllerBase
{
    protected static $internalServiceClass = '\OPNsense\Pushover\Pushover';
    protected static $internalServiceEnabled = 'general.Enabled';
    protected static $internalServiceTemplate = 'OPNsense/Pushover';
    protected static $internalServiceName = 'pushover';

    public function testAction()
    {
        if (!$this->request->isPost()) {
            $this->response->setStatusCode(405, 'Method Not Allowed');
            return ['status' => 'failed', 'code' => 'method_not_allowed', 'message' => 'POST required'];
        }
        $backend = new Backend();
        try {
            $rawOutput = $backend->configdRun(
                'pushover notify ' . rawurlencode('Test notification from OPNsense'),
                false,
                30
            );
        } catch (\Throwable $e) {
            syslog(LOG_ERR, 'pushover testAction: ' . substr($e->getMessage(), 0, 200));
            $this->response->setStatusCode(500, 'Internal Server Error');
            return ['status' => 'failed', 'code' => 'backend_error', 'message' => 'backend error, check system log'];
        }

        if (!is_string($rawOutput)) {
            syslog(LOG_ERR, 'pushover testAction: backend returned non-string output (type: ' . gettype($rawOutput) . ')');
            $this->response->setStatusCode(502, 'Bad Gateway');
            return ['status' => 'failed', 'code' => 'backend_error', 'message' => 'backend error, check system log'];
        }
        $output = trim($rawOutput);
        if (strlen($output) > 8192) {
            syslog(LOG_ERR, 'pushover testAction: backend output too large (length: ' . strlen($output) . ')');
            $this->response->setStatusCode(502, 'Bad Gateway');
            return ['status' => 'failed', 'code' => 'backend_error', 'message' => 'backend error, check system log'];
        }

        $result = json_decode($output, true);
        if (!is_array($result) || !isset($result['status']) || !is_string($result['status'])) {
            syslog(LOG_ERR, 'pushover testAction: unexpected backend output: ' . substr($output, 0, 200));
            $this->response->setStatusCode(502, 'Bad Gateway');
            return ['status' => 'failed', 'code' => 'backend_error', 'message' => 'backend error, check system log'];
        }

        $status = strtolower(trim($result['status']));
        if (!in_array($status, ['ok', 'failed'], true)) {
            syslog(LOG_ERR, 'pushover testAction: unexpected status: ' . substr($status, 0, 50));
            $this->response->setStatusCode(502, 'Bad Gateway');
            return ['status' => 'failed', 'code' => 'backend_error', 'message' => 'backend error, check system log'];
        }

        $msg = $result['message'] ?? null;
        $message = '';
        if (is_string($msg)) {
            $message = trim((string)preg_replace('/[\x00-\x1F\x7F]/', ' ', $msg));
            if (strlen($message) > 500) {
                $message = mb_strcut($message, 0, 500, 'UTF-8');
            }
        }
        if ($message === '') {
            $message = $status === 'ok' ? 'Notification sent' : 'backend error, check system log';
        }

        return ['status' => $status, 'code' => $status === 'ok' ? 'ok' : 'notify_failed', 'message' => $message];
    }
}
