# Generated by Django 3.2.19 on 2023-06-01 16:18

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Dept',
            fields=[
                ('id', models.BigAutoField(help_text='Id', primary_key=True, serialize=False, verbose_name='Id')),
                ('description', models.CharField(blank=True, help_text='描述', max_length=255, null=True, verbose_name='描述')),
                ('modifier', models.CharField(blank=True, help_text='修改人', max_length=255, null=True, verbose_name='修改人')),
                ('dept_belong_id', models.CharField(blank=True, help_text='数据归属部门', max_length=255, null=True, verbose_name='数据归属部门')),
                ('update_datetime', models.DateTimeField(auto_now=True, help_text='修改时间', null=True, verbose_name='修改时间')),
                ('create_datetime', models.DateTimeField(auto_now_add=True, help_text='创建时间', null=True, verbose_name='创建时间')),
                ('is_deleted', models.BooleanField(db_index=True, default=False, help_text='是否软删除', verbose_name='是否软删除')),
                ('name', models.CharField(help_text='部门名称', max_length=64, verbose_name='部门名称')),
                ('key', models.CharField(blank=True, help_text='部门字符', max_length=64, null=True, verbose_name='部门字符')),
                ('sort', models.IntegerField(default=1, help_text='显示排序', verbose_name='显示排序')),
                ('owner', models.CharField(blank=True, help_text='负责人', max_length=32, null=True, verbose_name='负责人')),
                ('phone', models.CharField(blank=True, help_text='联系电话', max_length=32, null=True, verbose_name='联系电话')),
                ('email', models.EmailField(blank=True, help_text='邮箱', max_length=32, null=True, verbose_name='邮箱')),
                ('status', models.BooleanField(blank=True, default=True, help_text='部门状态', null=True, verbose_name='部门状态')),
                ('creator', models.ForeignKey(db_constraint=False, help_text='创建人', null=True, on_delete=django.db.models.deletion.SET_NULL, related_query_name='creator_query', to=settings.AUTH_USER_MODEL, verbose_name='创建人')),
                ('parent', models.ForeignKey(blank=True, db_constraint=False, default=None, help_text='上级部门', null=True, on_delete=django.db.models.deletion.CASCADE, to='system.dept', verbose_name='上级部门')),
            ],
            options={
                'verbose_name': '部门表',
                'verbose_name_plural': '部门表',
                'db_table': 'system_dept',
                'ordering': ('sort',),
            },
        ),
        migrations.CreateModel(
            name='Menu',
            fields=[
                ('id', models.BigAutoField(help_text='Id', primary_key=True, serialize=False, verbose_name='Id')),
                ('description', models.CharField(blank=True, help_text='描述', max_length=255, null=True, verbose_name='描述')),
                ('modifier', models.CharField(blank=True, help_text='修改人', max_length=255, null=True, verbose_name='修改人')),
                ('dept_belong_id', models.CharField(blank=True, help_text='数据归属部门', max_length=255, null=True, verbose_name='数据归属部门')),
                ('update_datetime', models.DateTimeField(auto_now=True, help_text='修改时间', null=True, verbose_name='修改时间')),
                ('create_datetime', models.DateTimeField(auto_now_add=True, help_text='创建时间', null=True, verbose_name='创建时间')),
                ('is_deleted', models.BooleanField(db_index=True, default=False, help_text='是否软删除', verbose_name='是否软删除')),
                ('icon', models.CharField(blank=True, help_text='菜单图标', max_length=64, null=True, verbose_name='菜单图标')),
                ('name', models.CharField(help_text='菜单名称', max_length=64, verbose_name='菜单名称')),
                ('sort', models.IntegerField(blank=True, default=1, help_text='显示排序', null=True, verbose_name='显示排序')),
                ('is_link', models.BooleanField(default=False, help_text='是否外链', verbose_name='是否外链')),
                ('is_catalog', models.BooleanField(default=False, help_text='是否目录', verbose_name='是否目录')),
                ('web_path', models.CharField(blank=True, help_text='路由地址', max_length=128, null=True, verbose_name='路由地址')),
                ('component', models.CharField(blank=True, help_text='组件地址', max_length=128, null=True, verbose_name='组件地址')),
                ('component_name', models.CharField(blank=True, help_text='组件名称', max_length=50, null=True, verbose_name='组件名称')),
                ('status', models.BooleanField(blank=True, default=True, help_text='菜单状态', verbose_name='菜单状态')),
                ('cache', models.BooleanField(blank=True, default=False, help_text='是否页面缓存', verbose_name='是否页面缓存')),
                ('visible', models.BooleanField(blank=True, default=True, help_text='侧边栏中是否显示', verbose_name='侧边栏中是否显示')),
                ('creator', models.ForeignKey(db_constraint=False, help_text='创建人', null=True, on_delete=django.db.models.deletion.SET_NULL, related_query_name='creator_query', to=settings.AUTH_USER_MODEL, verbose_name='创建人')),
                ('parent', models.ForeignKey(blank=True, db_constraint=False, help_text='上级菜单', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='system.menu', verbose_name='上级菜单')),
            ],
            options={
                'verbose_name': '菜单表',
                'verbose_name_plural': '菜单表',
                'db_table': 'system_menu',
                'ordering': ('sort',),
            },
        ),
        migrations.CreateModel(
            name='MenuButton',
            fields=[
                ('id', models.BigAutoField(help_text='Id', primary_key=True, serialize=False, verbose_name='Id')),
                ('description', models.CharField(blank=True, help_text='描述', max_length=255, null=True, verbose_name='描述')),
                ('modifier', models.CharField(blank=True, help_text='修改人', max_length=255, null=True, verbose_name='修改人')),
                ('dept_belong_id', models.CharField(blank=True, help_text='数据归属部门', max_length=255, null=True, verbose_name='数据归属部门')),
                ('update_datetime', models.DateTimeField(auto_now=True, help_text='修改时间', null=True, verbose_name='修改时间')),
                ('create_datetime', models.DateTimeField(auto_now_add=True, help_text='创建时间', null=True, verbose_name='创建时间')),
                ('is_deleted', models.BooleanField(db_index=True, default=False, help_text='是否软删除', verbose_name='是否软删除')),
                ('name', models.CharField(help_text='名称', max_length=64, verbose_name='名称')),
                ('value', models.CharField(help_text='权限值', max_length=64, verbose_name='权限值')),
                ('api', models.CharField(help_text='接口地址', max_length=200, verbose_name='接口地址')),
                ('method', models.IntegerField(blank=True, default=0, help_text='接口请求方法', null=True, verbose_name='接口请求方法')),
                ('creator', models.ForeignKey(db_constraint=False, help_text='创建人', null=True, on_delete=django.db.models.deletion.SET_NULL, related_query_name='creator_query', to=settings.AUTH_USER_MODEL, verbose_name='创建人')),
                ('menu', models.ForeignKey(db_constraint=False, help_text='关联菜单', on_delete=django.db.models.deletion.CASCADE, related_name='menuPermission', to='system.menu', verbose_name='关联菜单')),
            ],
            options={
                'verbose_name': '菜单权限表',
                'verbose_name_plural': '菜单权限表',
                'db_table': 'system_menu_button',
                'ordering': ('-name',),
            },
        ),
        migrations.CreateModel(
            name='Role',
            fields=[
                ('id', models.BigAutoField(help_text='Id', primary_key=True, serialize=False, verbose_name='Id')),
                ('description', models.CharField(blank=True, help_text='描述', max_length=255, null=True, verbose_name='描述')),
                ('modifier', models.CharField(blank=True, help_text='修改人', max_length=255, null=True, verbose_name='修改人')),
                ('dept_belong_id', models.CharField(blank=True, help_text='数据归属部门', max_length=255, null=True, verbose_name='数据归属部门')),
                ('update_datetime', models.DateTimeField(auto_now=True, help_text='修改时间', null=True, verbose_name='修改时间')),
                ('create_datetime', models.DateTimeField(auto_now_add=True, help_text='创建时间', null=True, verbose_name='创建时间')),
                ('is_deleted', models.BooleanField(db_index=True, default=False, help_text='是否软删除', verbose_name='是否软删除')),
                ('name', models.CharField(help_text='角色名称', max_length=64, verbose_name='角色名称')),
                ('key', models.CharField(help_text='权限字符', max_length=64, unique=True, verbose_name='权限字符')),
                ('sort', models.IntegerField(default=1, help_text='角色顺序', verbose_name='角色顺序')),
                ('status', models.BooleanField(default=True, help_text='角色状态', verbose_name='角色状态')),
                ('admin', models.BooleanField(default=False, help_text='是否为admin', verbose_name='是否为admin')),
                ('data_range', models.IntegerField(choices=[(0, '仅本人数据权限'), (1, '本部门及以下数据权限'), (2, '本部门数据权限'), (3, '全部数据权限'), (4, '自定数据权限')], default=0, help_text='数据权限范围', verbose_name='数据权限范围')),
                ('remark', models.TextField(blank=True, help_text='备注', null=True, verbose_name='备注')),
                ('creator', models.ForeignKey(db_constraint=False, help_text='创建人', null=True, on_delete=django.db.models.deletion.SET_NULL, related_query_name='creator_query', to=settings.AUTH_USER_MODEL, verbose_name='创建人')),
                ('dept', models.ManyToManyField(db_constraint=False, help_text='数据权限-关联部门', to='system.Dept', verbose_name='数据权限-关联部门')),
                ('menu', models.ManyToManyField(db_constraint=False, help_text='关联菜单', to='system.Menu', verbose_name='关联菜单')),
                ('permission', models.ManyToManyField(db_constraint=False, help_text='关联菜单的接口按钮', to='system.MenuButton', verbose_name='关联菜单的接口按钮')),
            ],
            options={
                'verbose_name': '角色表',
                'verbose_name_plural': '角色表',
                'db_table': 'system_role',
                'ordering': ('sort',),
            },
        ),
        migrations.CreateModel(
            name='Post',
            fields=[
                ('id', models.BigAutoField(help_text='Id', primary_key=True, serialize=False, verbose_name='Id')),
                ('description', models.CharField(blank=True, help_text='描述', max_length=255, null=True, verbose_name='描述')),
                ('modifier', models.CharField(blank=True, help_text='修改人', max_length=255, null=True, verbose_name='修改人')),
                ('dept_belong_id', models.CharField(blank=True, help_text='数据归属部门', max_length=255, null=True, verbose_name='数据归属部门')),
                ('update_datetime', models.DateTimeField(auto_now=True, help_text='修改时间', null=True, verbose_name='修改时间')),
                ('create_datetime', models.DateTimeField(auto_now_add=True, help_text='创建时间', null=True, verbose_name='创建时间')),
                ('is_deleted', models.BooleanField(db_index=True, default=False, help_text='是否软删除', verbose_name='是否软删除')),
                ('name', models.CharField(help_text='岗位名称', max_length=64, verbose_name='岗位名称')),
                ('code', models.CharField(help_text='岗位编码', max_length=32, verbose_name='岗位编码')),
                ('sort', models.IntegerField(default=1, help_text='岗位顺序', verbose_name='岗位顺序')),
                ('status', models.IntegerField(choices=[(0, '离职'), (1, '在职')], default=1, help_text='岗位状态', verbose_name='岗位状态')),
                ('creator', models.ForeignKey(db_constraint=False, help_text='创建人', null=True, on_delete=django.db.models.deletion.SET_NULL, related_query_name='creator_query', to=settings.AUTH_USER_MODEL, verbose_name='创建人')),
            ],
            options={
                'verbose_name': '岗位表',
                'verbose_name_plural': '岗位表',
                'db_table': 'system_post',
                'ordering': ('sort',),
            },
        ),
        migrations.CreateModel(
            name='OperationLog',
            fields=[
                ('id', models.BigAutoField(help_text='Id', primary_key=True, serialize=False, verbose_name='Id')),
                ('description', models.CharField(blank=True, help_text='描述', max_length=255, null=True, verbose_name='描述')),
                ('modifier', models.CharField(blank=True, help_text='修改人', max_length=255, null=True, verbose_name='修改人')),
                ('dept_belong_id', models.CharField(blank=True, help_text='数据归属部门', max_length=255, null=True, verbose_name='数据归属部门')),
                ('update_datetime', models.DateTimeField(auto_now=True, help_text='修改时间', null=True, verbose_name='修改时间')),
                ('create_datetime', models.DateTimeField(auto_now_add=True, help_text='创建时间', null=True, verbose_name='创建时间')),
                ('is_deleted', models.BooleanField(db_index=True, default=False, help_text='是否软删除', verbose_name='是否软删除')),
                ('request_modular', models.CharField(blank=True, help_text='请求模块', max_length=64, null=True, verbose_name='请求模块')),
                ('request_path', models.CharField(blank=True, help_text='请求地址', max_length=400, null=True, verbose_name='请求地址')),
                ('request_body', models.TextField(blank=True, help_text='请求参数', null=True, verbose_name='请求参数')),
                ('request_method', models.CharField(blank=True, help_text='请求方式', max_length=8, null=True, verbose_name='请求方式')),
                ('request_msg', models.TextField(blank=True, help_text='操作说明', null=True, verbose_name='操作说明')),
                ('request_ip', models.CharField(blank=True, help_text='请求ip地址', max_length=32, null=True, verbose_name='请求ip地址')),
                ('request_browser', models.CharField(blank=True, help_text='请求浏览器', max_length=64, null=True, verbose_name='请求浏览器')),
                ('response_code', models.CharField(blank=True, help_text='响应状态码', max_length=32, null=True, verbose_name='响应状态码')),
                ('request_os', models.CharField(blank=True, help_text='操作系统', max_length=64, null=True, verbose_name='操作系统')),
                ('json_result', models.TextField(blank=True, help_text='返回信息', null=True, verbose_name='返回信息')),
                ('status', models.BooleanField(default=False, help_text='响应状态', verbose_name='响应状态')),
                ('creator', models.ForeignKey(db_constraint=False, help_text='创建人', null=True, on_delete=django.db.models.deletion.SET_NULL, related_query_name='creator_query', to=settings.AUTH_USER_MODEL, verbose_name='创建人')),
            ],
            options={
                'verbose_name': '操作日志',
                'verbose_name_plural': '操作日志',
                'db_table': 'system_operation_log',
                'ordering': ('-create_datetime',),
            },
        ),
        migrations.CreateModel(
            name='LoginLog',
            fields=[
                ('id', models.BigAutoField(help_text='Id', primary_key=True, serialize=False, verbose_name='Id')),
                ('description', models.CharField(blank=True, help_text='描述', max_length=255, null=True, verbose_name='描述')),
                ('modifier', models.CharField(blank=True, help_text='修改人', max_length=255, null=True, verbose_name='修改人')),
                ('dept_belong_id', models.CharField(blank=True, help_text='数据归属部门', max_length=255, null=True, verbose_name='数据归属部门')),
                ('update_datetime', models.DateTimeField(auto_now=True, help_text='修改时间', null=True, verbose_name='修改时间')),
                ('create_datetime', models.DateTimeField(auto_now_add=True, help_text='创建时间', null=True, verbose_name='创建时间')),
                ('is_deleted', models.BooleanField(db_index=True, default=False, help_text='是否软删除', verbose_name='是否软删除')),
                ('username', models.CharField(blank=True, help_text='登录用户名', max_length=32, null=True, verbose_name='登录用户名')),
                ('ip', models.CharField(blank=True, help_text='登录ip', max_length=32, null=True, verbose_name='登录ip')),
                ('agent', models.TextField(blank=True, help_text='agent信息', null=True, verbose_name='agent信息')),
                ('browser', models.CharField(blank=True, help_text='浏览器名', max_length=200, null=True, verbose_name='浏览器名')),
                ('os', models.CharField(blank=True, help_text='操作系统', max_length=200, null=True, verbose_name='操作系统')),
                ('continent', models.CharField(blank=True, help_text='州', max_length=50, null=True, verbose_name='州')),
                ('country', models.CharField(blank=True, help_text='国家', max_length=50, null=True, verbose_name='国家')),
                ('province', models.CharField(blank=True, help_text='省份', max_length=50, null=True, verbose_name='省份')),
                ('city', models.CharField(blank=True, help_text='城市', max_length=50, null=True, verbose_name='城市')),
                ('district', models.CharField(blank=True, help_text='县区', max_length=50, null=True, verbose_name='县区')),
                ('isp', models.CharField(blank=True, help_text='运营商', max_length=50, null=True, verbose_name='运营商')),
                ('area_code', models.CharField(blank=True, help_text='区域代码', max_length=50, null=True, verbose_name='区域代码')),
                ('country_english', models.CharField(blank=True, help_text='英文全称', max_length=50, null=True, verbose_name='英文全称')),
                ('country_code', models.CharField(blank=True, help_text='简称', max_length=50, null=True, verbose_name='简称')),
                ('longitude', models.CharField(blank=True, help_text='经度', max_length=50, null=True, verbose_name='经度')),
                ('latitude', models.CharField(blank=True, help_text='纬度', max_length=50, null=True, verbose_name='纬度')),
                ('login_type', models.IntegerField(choices=[(1, '普通登录')], default=1, help_text='登录类型', verbose_name='登录类型')),
                ('creator', models.ForeignKey(db_constraint=False, help_text='创建人', null=True, on_delete=django.db.models.deletion.SET_NULL, related_query_name='creator_query', to=settings.AUTH_USER_MODEL, verbose_name='创建人')),
            ],
            options={
                'verbose_name': '登录日志',
                'verbose_name_plural': '登录日志',
                'db_table': 'system_login_log',
                'ordering': ('-create_datetime',),
            },
        ),
        migrations.CreateModel(
            name='Area',
            fields=[
                ('id', models.BigAutoField(help_text='Id', primary_key=True, serialize=False, verbose_name='Id')),
                ('description', models.CharField(blank=True, help_text='描述', max_length=255, null=True, verbose_name='描述')),
                ('modifier', models.CharField(blank=True, help_text='修改人', max_length=255, null=True, verbose_name='修改人')),
                ('dept_belong_id', models.CharField(blank=True, help_text='数据归属部门', max_length=255, null=True, verbose_name='数据归属部门')),
                ('update_datetime', models.DateTimeField(auto_now=True, help_text='修改时间', null=True, verbose_name='修改时间')),
                ('create_datetime', models.DateTimeField(auto_now_add=True, help_text='创建时间', null=True, verbose_name='创建时间')),
                ('is_deleted', models.BooleanField(db_index=True, default=False, help_text='是否软删除', verbose_name='是否软删除')),
                ('name', models.CharField(help_text='名称', max_length=100, verbose_name='名称')),
                ('code', models.CharField(db_index=True, help_text='地区编码', max_length=20, unique=True, verbose_name='地区编码')),
                ('level', models.BigIntegerField(help_text='地区层级(1省份 2城市 3区县 4乡级)', verbose_name='地区层级(1省份 2城市 3区县 4乡级)')),
                ('pinyin', models.CharField(help_text='拼音', max_length=255, verbose_name='拼音')),
                ('initials', models.CharField(help_text='首字母', max_length=20, verbose_name='首字母')),
                ('enable', models.BooleanField(default=True, help_text='是否启用', verbose_name='是否启用')),
                ('creator', models.ForeignKey(db_constraint=False, help_text='创建人', null=True, on_delete=django.db.models.deletion.SET_NULL, related_query_name='creator_query', to=settings.AUTH_USER_MODEL, verbose_name='创建人')),
                ('pcode', models.ForeignKey(blank=True, db_constraint=False, help_text='父地区编码', null=True, on_delete=django.db.models.deletion.CASCADE, to='system.area', to_field='code', verbose_name='父地区编码')),
            ],
            options={
                'verbose_name': '地区表',
                'verbose_name_plural': '地区表',
                'db_table': 'system_area',
                'ordering': ('code',),
            },
        ),
        migrations.CreateModel(
            name='ApiWhiteList',
            fields=[
                ('id', models.BigAutoField(help_text='Id', primary_key=True, serialize=False, verbose_name='Id')),
                ('description', models.CharField(blank=True, help_text='描述', max_length=255, null=True, verbose_name='描述')),
                ('modifier', models.CharField(blank=True, help_text='修改人', max_length=255, null=True, verbose_name='修改人')),
                ('dept_belong_id', models.CharField(blank=True, help_text='数据归属部门', max_length=255, null=True, verbose_name='数据归属部门')),
                ('update_datetime', models.DateTimeField(auto_now=True, help_text='修改时间', null=True, verbose_name='修改时间')),
                ('create_datetime', models.DateTimeField(auto_now_add=True, help_text='创建时间', null=True, verbose_name='创建时间')),
                ('is_deleted', models.BooleanField(db_index=True, default=False, help_text='是否软删除', verbose_name='是否软删除')),
                ('url', models.CharField(help_text='url地址', max_length=200, verbose_name='url')),
                ('method', models.IntegerField(blank=True, default=0, help_text='接口请求方法', null=True, verbose_name='接口请求方法')),
                ('enable_datasource', models.BooleanField(blank=True, default=True, help_text='激活数据权限', verbose_name='激活数据权限')),
                ('creator', models.ForeignKey(db_constraint=False, help_text='创建人', null=True, on_delete=django.db.models.deletion.SET_NULL, related_query_name='creator_query', to=settings.AUTH_USER_MODEL, verbose_name='创建人')),
            ],
            options={
                'verbose_name': '接口白名单',
                'verbose_name_plural': '接口白名单',
                'db_table': 'api_white_list',
                'ordering': ('-create_datetime',),
            },
        ),
    ]
