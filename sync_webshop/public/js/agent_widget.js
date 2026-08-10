// Floating assistant for the ERPNext Desk.
//
// Calls the same endpoint as Telegram, so the answers and the permission rules
// are identical — whoever is logged in sees only what they could open here
// anyway. Read-only: the assistant has no write path.

frappe.provide('dpono.agent');

dpono.agent = {
	config: null,
	messages: [],

	init() {
		if (document.getElementById('dpono-agent-launcher')) return;
		if (frappe.session.user === 'Guest') return;

		frappe.call({
			method: 'sync_webshop.api.agent.get_agent_config',
			callback: (r) => {
				if (!r.message || !r.message.enabled) return;
				this.config = r.message;
				this.render();
			},
			error: () => {},
		});
	},

	render() {
		const launcher = document.createElement('button');
		launcher.id = 'dpono-agent-launcher';
		launcher.title = this.config.name;
		launcher.setAttribute('aria-label', this.config.name);
		launcher.innerHTML = '<span>💬</span>';
		launcher.onclick = () => this.toggle();
		document.body.appendChild(launcher);

		const panel = document.createElement('div');
		panel.id = 'dpono-agent-panel';
		panel.setAttribute('dir', 'rtl');
		panel.innerHTML = `
			<div class="da-head">
				<span>${frappe.utils.escape_html(this.config.name)}</span>
				<button class="da-close" aria-label="اقفل">✕</button>
			</div>
			<div class="da-body"></div>
			<div class="da-chips"></div>
			<form class="da-form">
				<input type="text" placeholder="اسأل عن المبيعات أو الطلبات أو المخزون…" maxlength="300" />
				<button type="submit">ابعت</button>
			</form>`;
		document.body.appendChild(panel);

		panel.querySelector('.da-close').onclick = () => this.toggle();
		panel.querySelector('.da-form').onsubmit = (e) => {
			e.preventDefault();
			const input = panel.querySelector('input');
			const text = input.value.trim();
			if (!text) return;
			input.value = '';
			this.ask(text);
		};

		this.say('bot', this.config.greeting || 'أهلاً.');

		const chips = panel.querySelector('.da-chips');
		(this.config.examples || []).forEach((ex) => {
			if (!ex.example_question) return;
			const chip = document.createElement('button');
			chip.type = 'button';
			chip.textContent = ex.example_question;
			chip.onclick = () => this.ask(ex.example_question);
			chips.appendChild(chip);
		});
	},

	toggle() {
		const panel = document.getElementById('dpono-agent-panel');
		panel.classList.toggle('open');
		if (panel.classList.contains('open')) panel.querySelector('input').focus();
	},

	say(who, text) {
		const body = document.querySelector('#dpono-agent-panel .da-body');
		const div = document.createElement('div');
		div.className = 'da-msg da-' + who;
		// Replies are built server-side from named queries; **bold** is the only
		// markup used, so escape everything else before rendering it.
		div.innerHTML = frappe.utils
			.escape_html(text)
			.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
			.replace(/\n/g, '<br>');
		body.appendChild(div);
		body.scrollTop = body.scrollHeight;
	},

	ask(question) {
		this.say('user', question);
		const body = document.querySelector('#dpono-agent-panel .da-body');
		const wait = document.createElement('div');
		wait.className = 'da-msg da-bot da-wait';
		wait.textContent = '…';
		body.appendChild(wait);
		body.scrollTop = body.scrollHeight;

		frappe.call({
			method: 'sync_webshop.api.agent.ask',
			args: { question },
			callback: (r) => {
				wait.remove();
				this.say('bot', (r.message && r.message.reply) || 'مفيش رد.');
			},
			error: () => {
				wait.remove();
				this.say('bot', 'حصل خطأ. جرّب تاني.');
			},
		});
	},
};

$(document).on('app_ready', () => dpono.agent.init());
$(document).ready(() => setTimeout(() => dpono.agent.init(), 1500));
