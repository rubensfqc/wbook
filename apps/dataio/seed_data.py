"""Demo content. Dates are day offsets from today; times are local wall-clock. Never real patient data or photos."""

OPERATORS = [
    {"email": "carla@wbook.example", "name": "Carla Operadora"},
    {"email": "rui@wbook.example", "name": "Rui Suporte"},
]

CLINICS = [
    {
        "key": "sorriso", "slug": "clinica-sorriso", "email": "ana@sorriso.example", "name": "Ana Lima",
        "display_name": "Dra. Ana Lima", "clinic_name": "Clínica Sorriso", "cro": "12345", "uf": "SP", "city": "São Paulo",
        "address": "Rua das Flores, 123 — Pinheiros", "whatsapp": "11987650001", "phone": "1130450001",
        "colour": (15, 118, 110), "accent": "teal", "paid_days": 120, "trial_days": 14, "visible_slots": 4,
        "headline": "Seu sorriso em boas mãos",
        "about": "Atendimento odontológico completo, com foco em prevenção, estética e conforto. Mais de 12 anos cuidando de famílias em Pinheiros.",
        "services": "Limpeza e prevenção\nClareamento\nRestaurações estéticas\nImplantes\nAlinhadores invisíveis",
        "specialties": "Clínica geral\nEstética dental\nImplantodontia",
        "patients": [
            ("maria", "Maria Silva", "maria@paciente.example", "11991110001"),
            ("joao", "João Pereira", "joao@paciente.example", "11991110002"),
            ("luiza", "Luiza Andrade", "luiza@paciente.example", "11991110003"),
            ("pedro", "Pedro Costa", "pedro@paciente.example", "11991110004"),
            ("beatriz", "Beatriz Rocha", "beatriz@paciente.example", "11991110005"),
            ("rafael", "Rafael Gomes", "rafael@paciente.example", "11991110006"),
            ("camila", "Camila Nunes", "camila@paciente.example", "11991110007"),
            ("thiago", "Thiago Alves", "thiago@paciente.example", "11991110008"),
        ],
        "leads": [
            ("fernanda", "Fernanda Lopes", "fernanda@lead.example", "11992220001", "Gostaria de saber sobre clareamento."),
            ("gustavo", "Gustavo Martins", "gustavo@lead.example", "11992220002", "Tenho uma dor no dente do siso."),
        ],
        "treatments": [
            ("maria", "aligners", "Ortodontia — alinhadores", "Arcadas superior e inferior", "IN_PROGRESS", 45, 12, "8500.00"),
            ("joao", "implant", "Implante 36", "36", "IN_PROGRESS", 60, 4, "4200.00"),
            ("luiza", "whitening", "Clareamento", "Arcadas", "COMPLETED", 100, 3, "1200.00"),
        ],
    },
    {
        "key": "ipe", "slug": "odonto-ipe", "email": "paulo@odontoipe.example", "name": "Paulo Reis",
        "display_name": "Dr. Paulo Reis", "clinic_name": "Odonto Ipê", "cro": "54321", "uf": "MG", "city": "Belo Horizonte",
        "address": "Av. do Contorno, 900 — Funcionários", "whatsapp": "31987650002", "phone": "3132220002",
        "colour": (29, 78, 216), "accent": "ocean", "paid_days": 0, "trial_days": 14, "visible_slots": 0,
        "headline": "Odontologia para toda a família",
        "about": "Consultório acolhedor, com horários flexíveis e atendimento infantil.",
        "services": "Odontopediatria\nCanal\nPróteses\nLimpeza",
        "specialties": "Odontopediatria\nEndodontia",
        "patients": [
            ("ana", "Ana Beatriz Souza", "anabeatriz@paciente.example", "31991110001"),
            ("carlos", "Carlos Mendes", "carlos@paciente.example", "31991110002"),
            ("julia", "Júlia Ferreira", "julia@paciente.example", "31991110003"),
            ("lucas", "Lucas Barbosa", "lucas@paciente.example", "31991110004"),
        ],
        "leads": [("helena", "Helena Dias", "helena@lead.example", "31992220001", "Vocês atendem crianças de 4 anos?")],
        "treatments": [("carlos", "canal", "Tratamento de canal 46", "46", "IN_PROGRESS", 50, 3, "1500.00")],
    },
    {
        "key": "mais", "slug": "sorria-mais", "email": "lia@sorriamais.example", "name": "Lia Campos",
        "display_name": "Dra. Lia Campos", "clinic_name": "Sorria Mais", "cro": "77777", "uf": "RJ", "city": "Rio de Janeiro",
        "address": "Rua Visconde de Pirajá, 50 — Ipanema", "whatsapp": "21987650003", "phone": "2125550003",
        "colour": (126, 58, 110), "accent": "plum", "paid_days": -10, "trial_days": 0, "visible_slots": 4,
        "headline": "Estética do sorriso", "about": "Consultório focado em estética.", "services": "Facetas\nClareamento",
        "specialties": "Dentística", "patients": [("rita", "Rita Moura", "rita@paciente.example", "21991110001")],
        "leads": [], "treatments": [],
    },
]
