// 中文姓氏库
const chineseSurnames = [
    '王', '李', '张', '刘', '陈', '杨', '黄', '赵', '吴', '周',
    '徐', '孙', '马', '朱', '胡', '郭', '何', '高', '林', '罗',
    '郑', '梁', '谢', '宋', '唐', '许', '韩', '冯', '邓', '曹',
    '彭', '曾', '萧', '田', '董', '袁', '潘', '于', '蒋', '蔡',
    '余', '杜', '叶', '程', '苏', '魏', '吕', '丁', '任', '沈'
];

// 男性名字用字
const maleNameChars = [
    '伟', '刚', '勇', '毅', '俊', '峰', '强', '平', '保', '东',
    '文', '辉', '力', '明', '永', '健', '世', '广', '志', '义',
    '兴', '良', '海', '山', '仁', '波', '宁', '贵', '福', '生',
    '龙', '元', '全', '国', '胜', '学', '祥', '才', '发', '武',
    '新', '利', '清', '飞', '彬', '富', '顺', '信', '子', '杰',
    '涛', '昌', '成', '康', '星', '光', '天', '达', '安', '岩',
    '中', '茂', '进', '林', '有', '坚', '和', '彪', '博', '诚',
    '先', '敬', '震', '振', '壮', '会', '思', '群', '豪', '心',
    '邦', '承', '乐', '绍', '功', '松', '善', '厚', '庆', '磊',
    '民', '友', '裕', '河', '哲', '江', '超', '浩', '亮', '政'
];

// 女性名字用字
const femaleNameChars = [
    '秀', '娟', '英', '华', '慧', '巧', '美', '娜', '静', '淑',
    '惠', '珠', '翠', '雅', '芝', '玉', '萍', '红', '娥', '玲',
    '芬', '芳', '燕', '彩', '春', '菊', '兰', '凤', '洁', '梅',
    '琳', '素', '云', '莲', '真', '环', '雪', '荣', '爱', '妹',
    '霞', '香', '月', '莺', '媛', '艳', '瑞', '凡', '佳', '嘉',
    '琼', '勤', '珍', '贞', '莉', '桂', '娣', '叶', '璧', '璐',
    '娅', '琦', '晶', '妍', '茜', '秋', '珊', '莎', '锦', '黛',
    '青', '倩', '婷', '姣', '婉', '娴', '瑾', '颖', '露', '瑶',
    '怡', '婵', '雁', '蓓', '纨', '仪', '荷', '映', '蓉', '柔',
    '竹', '岚', '薇', '宝', '韵', '蕊', '芝', '琪', '伊', '媚'
];

// 英文名字库 - 传统
const traditionalNames = {
    male: ['James', 'William', 'Charles', 'George', 'Thomas', 'Richard', 'Joseph', 'Edward', 'Henry', 'Arthur', 'Robert', 'John', 'Michael', 'David', 'Robert'],
    female: ['Elizabeth', 'Mary', 'Margaret', 'Sarah', 'Anne', 'Catherine', 'Jane', 'Alice', 'Victoria', 'Emily', 'Dorothy', 'Helen', 'Grace', 'Ruth', 'Frances']
};

// 英文名字库 - 现代
const modernNames = {
    male: ['Liam', 'Noah', 'Ethan', 'Mason', 'Lucas', 'Logan', 'Aiden', 'Carter', 'Owen', 'Jack', 'Elijah', 'Jackson', 'Grayson', 'Michael', 'Benjamin'],
    female: ['Emma', 'Olivia', 'Ava', 'Sophia', 'Isabella', 'Mia', 'Charlotte', 'Amelia', 'Harper', 'Evelyn', 'Abigail', 'Emily', 'Elizabeth', 'Avery', 'Ella']
};

// 英文名字库 - 独特
const uniqueNames = {
    male: ['Zephyr', 'Orion', 'Atlas', 'Phoenix', 'Leo', 'Jasper', 'Archer', 'Finn', 'Theo', 'Ezra', 'Silas', 'Felix', 'Elian', 'Kai', 'Rylan'],
    female: ['Aria', 'Luna', 'Nova', 'Stella', 'Willow', 'Aurora', 'Hazel', 'Ivy', 'Vera', 'Luna', 'Elara', 'Lyra', 'Freya', 'Kaia', 'Sage']
};

// DOM 元素
const nameTypeSelect = document.getElementById('nameType');
const genderSelect = document.getElementById('gender');
const nameCountInput = document.getElementById('nameCount');
const nameLengthSelect = document.getElementById('nameLength');
const nameStyleSelect = document.getElementById('nameStyle');
const generateBtn = document.getElementById('generateBtn');
const copyBtn = document.getElementById('copyBtn');
const nameListDiv = document.getElementById('nameList');
const chineseOptions = document.querySelector('.chinese-options');
const englishOptions = document.querySelector('.english-options');

// 人名类型切换事件
nameTypeSelect.addEventListener('change', () => {
    const type = nameTypeSelect.value;
    if (type === 'chinese') {
        chineseOptions.style.display = 'block';
        englishOptions.style.display = 'none';
    } else {
        chineseOptions.style.display = 'none';
        englishOptions.style.display = 'block';
    }
});

// 生成中文人名
function generateChineseName(gender, length) {
    const surname = chineseSurnames[Math.floor(Math.random() * chineseSurnames.length)];
    let givenName = '';
    let actualGender = gender;

    let chars;
    if (gender === 'male') {
        chars = maleNameChars;
    } else if (gender === 'female') {
        chars = femaleNameChars;
    } else {
        chars = [...maleNameChars, ...femaleNameChars];
        actualGender = Math.random() > 0.5 ? 'male' : 'female';
    }

    let nameLength = length;
    if (length === 'random') {
        nameLength = Math.random() > 0.7 ? 2 : 1;
    }

    for (let i = 0; i < nameLength; i++) {
        givenName += chars[Math.floor(Math.random() * chars.length)];
    }

    return {
        name: surname + givenName,
        gender: actualGender
    };
}

// 生成英文人名
function generateEnglishName(gender, style) {
    let names;
    switch (style) {
        case 'traditional':
            names = traditionalNames;
            break;
        case 'modern':
            names = modernNames;
            break;
        case 'unique':
            names = uniqueNames;
            break;
    }

    let genderKey;
    if (gender === 'male') {
        genderKey = 'male';
    } else if (gender === 'female') {
        genderKey = 'female';
    } else {
        genderKey = Math.random() > 0.5 ? 'male' : 'female';
    }

    return {
        name: names[genderKey][Math.floor(Math.random() * names[genderKey].length)],
        gender: genderKey
    };
}

// 生成人名
function generateNames() {
    const nameType = nameTypeSelect.value;
    const gender = genderSelect.value;
    const count = parseInt(nameCountInput.value);
    const nameLength = nameLengthSelect.value;
    const nameStyle = nameStyleSelect.value;

    let names = [];
    for (let i = 0; i < count; i++) {
        if (nameType === 'chinese') {
            names.push(generateChineseName(gender, nameLength));
        } else {
            names.push(generateEnglishName(gender, nameStyle));
        }
    }

    displayNames(names);
}

// 显示生成的名字
function displayNames(names) {
    nameListDiv.innerHTML = '';
    names.forEach(item => {
        const nameItem = document.createElement('div');
        nameItem.className = 'name-item';
        nameItem.dataset.gender = item.gender;

        const nameText = document.createElement('div');
        nameText.className = 'name-text';
        nameText.textContent = item.name;

        const genderTag = document.createElement('span');
        genderTag.className = `gender-tag gender-${item.gender}`;
        genderTag.textContent = item.gender === 'male' ? '男' : '女';

        nameItem.appendChild(nameText);
        nameItem.appendChild(genderTag);

        nameItem.onclick = function() {
            const genderText = item.gender === 'male' ? '男' : '女';
            const textToCopy = `${item.name}\t${genderText}`;
            navigator.clipboard.writeText(textToCopy);
            nameItem.style.background = '#667eea';
            nameText.style.color = 'white';
            genderTag.style.color = 'white';
            setTimeout(() => {
                nameItem.style.background = 'white';
                nameText.style.color = '#333';
                genderTag.style.color = '';
            }, 300);
        };
        nameListDiv.appendChild(nameItem);
    });
}

// 复制所有结果
function copyAllNames() {
    const nameItems = document.querySelectorAll('.name-item');
    const names = Array.from(nameItems).map(item => {
        const nameText = item.querySelector('.name-text').textContent;
        const genderText = item.querySelector('.gender-tag').textContent;
        return `${nameText}\t${genderText}`;
    }).join('\n');
    if (names) {
        navigator.clipboard.writeText(names);
        alert('已复制到剪贴板！可直接粘贴到 Excel，会自动分成两列');
    }
}

// 事件监听
generateBtn.addEventListener('click', generateNames);
copyBtn.addEventListener('click', copyAllNames);

// 页面加载时生成一些示例名字
window.addEventListener('load', () => {
    generateNames();
});
