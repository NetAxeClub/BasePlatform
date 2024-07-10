import os
from datetime import datetime

from git import Actor
from git import Repo
from pydriller import Repository
from netaxe.settings import BASE_DIR
repo_path = os.path.join(BASE_DIR, 'media/device_config')

if not os.path.exists(os.path.join(BASE_DIR, 'media/device_config')):
    os.makedirs(os.path.join(BASE_DIR, 'media/device_config'))
    repo = Repo.init(os.path.join(repo_path))

try:
    repo = Repo(path=repo_path)
except:
    repo = Repo.init(os.path.join(repo_path))


class ConfigGit:
    def __init__(self):
        self.repo = repo

    # 获取所有的提交
    def get_commit(self, commit=None):
        """
        {
          label: "Everybody's Got Something to Hide Except Me and My Monkey",
          value: 'song0',
          disabled: true
        },
        :param commit:
        :return:
        """
        result = []
        if commit is None:
            for m in repo.iter_commits():
                _data = {
                    # 'author': m.author,
                    'label': m.committed_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                    # 'message': m.message,
                    'value': m.hexsha,
                }
                result.append(_data)
        return result

    # 获取单个文件在commit范围中的变化
    def get_commit_by_file(self, **kwargs):
        file = kwargs['file']
        from_commit = kwargs['from_commit']
        to_commit = kwargs['to_commit']
        result = {
            'new_str': '无变更',
            'old_str': '无变更'
        }
        for commit in Repository(repo_path, from_commit=from_commit, to_commit=to_commit,
                                 filepath=file).traverse_commits():
            for m in commit.modified_files:
                if m.filename == file.split('/')[-1]:
                    result['new_str'] = m.source_code if m.source_code is not None else ''
                    result['old_str'] = m.source_code_before if m.source_code_before is not None else ''
                    result['added_lines'] = m.added_lines
                    result['deleted_lines'] = m.deleted_lines
                    return result
        return result

    def get_commit_by_file_new(self, **kwargs):
        file_path = kwargs['file']
        from_commit = repo.commit(kwargs['from_commit'])
        to_commit = repo.commit(kwargs['to_commit'])
        from_blob = from_commit.tree / file_path
        to_blob = to_commit.tree / file_path
        result = {
            'new_str': to_blob.data_stream.read().decode('utf-8'),
            'old_str': from_blob.data_stream.read().decode('utf-8')
        }
        return result

    # 获取单个commit包含的变更文件
    def get_commit_detail(self, commit):
        result = []
        for commit in Repository(repo_path, single=commit).traverse_commits():
            for m in commit.modified_files:
                tmp = {
                    'label': m.filename,
                    'value': m.new_path
                }
                result.append(tmp)
        return result

    # 获取单个commit指定文件名的变更详情
    def get_commit_modified_by_filename(self, commit, filename):
        result = {
            'new_str': '无变更',
            'old_str': '无变更'
        }
        for commit in Repository(repo_path, single=commit).traverse_commits():
            for m in commit.modified_files:
                if m.filename == filename.split('/')[-1]:
                    result['new_str'] = m.source_code if m.source_code is not None else ''
                    result['old_str'] = m.source_code_before if m.source_code_before is not None else ''
                    result['added_lines'] = m.added_lines
                    result['deleted_lines'] = m.deleted_lines
                    # print(m.added_lines)
                    return result
        return result

    def get_commit_file_content(self, commit, filename):
        commit = repo.commit(commit)
        blob = commit.tree / filename
        result = {
            'new_str': blob.data_stream.read().decode('utf-8'),
            'old_str': blob.data_stream.read().decode('utf-8')
        }
        return result

    def get_file_all_change_commmit(self, file_path):
        result = []
        for commit in repo.iter_commits():
            # 检查每个commit的变更文件
            for diff in commit.diff(commit.parents, paths=[file_path], create_patch=True):
                # 如果变更文件包含指定文件，将commit添加到列表中
                if diff.a_path == file_path or diff.b_path == file_path:
                    # commits.append(commit)
                    _data = {
                        # 'author': m.author,
                        'label': commit.committed_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                        # 'message': m.message,
                        'value': commit.hexsha,
                    }
                    result.append(_data)
        return result

    # 获取指定文件在指定日期的所有commit
<<<<<<< HEAD
<<<<<<< HEAD
    def get_file_commit_filter_by_date(self, file_path: str, date: str):
        result = []
        # 遍历commits
        for commit in repo.iter_commits(paths=file_path):
            print("Commit ID:", commit.hexsha)
            print("Author:", commit.author)
            print("Date:", commit.authored_datetime)
            print("Subject:", commit.message)
            print("-" * 40)  # 打印分隔符
            if str(commit.authored_datetime).startswith(date):
                _data = {
                    # 'author': m.author,
                    'label': commit.committed_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                    # 'message': m.message,
                    'value': commit.hexsha,
                }
                result.append(_data)
        return result
=======
=======
>>>>>>> 0c254d08ae6d937b64120deea702a3025644e1e8
    def get_file_content_by_commit(self, file_path: str, commit_hash: str):
        try:
            repo = Repo(repo_path)
            commit = repo.commit(commit_hash)
            tree = commit.tree
            file_blob = tree[file_path]
            # result = []
            # # 遍历commits
            # for commit in repo.iter_commits(paths=file_path):
            #     print("Commit ID:", commit.hexsha)
            #     print("Author:", commit.author)
            #     print("Date:", commit.authored_datetime)
            #     print("Subject:", commit.message)
            #     print("-" * 40)  # 打印分隔符
            #     if str(commit.authored_datetime).startswith(date):
            #         _data = {
            #             # 'author': m.author,
            #             'label': commit.committed_datetime.strftime('%Y-%m-%d %H:%M:%S'),
            #             # 'message': m.message,
            #             'value': commit.hexsha,
            #         }
            #         result.append(_data)
            return file_blob.data_stream.read().decode('utf-8')
        except Exception as e:
            return f"错误，没有获取到改commit的文件内容{str(e)}"
<<<<<<< HEAD
>>>>>>> 7c46413f37a900620783da4ddab4da9840d899b5
=======
>>>>>>> 0c254d08ae6d937b64120deea702a3025644e1e8


def push_file():
    # 本地更改的文件
    log_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    files = []
    changedFiles = [item.a_path for item in repo.index.diff(None)]
    files += changedFiles
    # 未跟踪的文件
    untracked_files = repo.untracked_files
    files += untracked_files
    if files:
        for file in files:
            repo.index.add(os.path.join(repo.working_tree_dir, file))
        author = Actor("netaxe", "netaxe@example.com")
        committer = Actor(log_time, "netops@example.com")
        commit = repo.index.commit(f"automation commit by {log_time}", author=author, committer=committer)
        if repo.remotes:
            for _origin in repo.remotes:
                repo.remote(_origin.name).push()
                o = repo.remotes.origin
                o.pull()
        return commit, changedFiles, untracked_files
    return '', '', ''


def test():
    commit1 = repo.commit('7c71676e4260f4ff800a75abcfac75bf3277f4c')
    commit2 = repo.commit('e3d6cfd54990921b23ad88803105302b629a7228')

    diff = commit1.diff(commit2)
    for change in diff.iter_change_type('T'):
        if change.a_path == '/path/to/your/file':
            print(change.diff)